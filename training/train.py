import os
import sys
import argparse
import yaml
import logging
import glob
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast, GradScaler
import xarray as xr
from tqdm import tqdm

# Add project root to sys.path to import backend modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.model.architecture import ConvLSTM3D_Enhanced
from training.loss import CombinedLoss

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Dataset Class ---
class StormDataset(Dataset):
    def __init__(self, data_dir, input_steps, prediction_steps, img_height, img_width, transform=None, min_dbz=0.0, max_dbz=70.0):
        self.data_dir = data_dir
        self.input_steps = input_steps
        self.prediction_steps = prediction_steps
        self.img_height = img_height
        self.img_width = img_width
        self.transform = transform
        self.min_dbz = min_dbz
        self.max_dbz = max_dbz
        
        # Find all NetCDF files
        self.files = sorted(glob.glob(os.path.join(data_dir, "*.nc")))
        
        # Create valid sequences
        self.sequences = []
        total_len = input_steps + prediction_steps
        
        # Simple sliding window
        # In a real scenario, check for time continuity!
        for i in range(len(self.files) - total_len + 1):
            self.sequences.append(self.files[i : i + total_len])
            
        logger.info(f"Found {len(self.files)} files. Created {len(self.sequences)} sequences.")

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        file_paths = self.sequences[idx]
        frames = []
        
        for p in file_paths:
            try:
                with xr.open_dataset(p, mask_and_scale=True, decode_times=False) as ds:
                    # Assuming variable name is 'DBZ' or similar, check config or standard
                    # Fallback to first variable if 'DBZ' not found
                    var_name = 'DBZ' if 'DBZ' in ds else list(ds.data_vars)[0]
                    data = ds[var_name].values
                    
                    # Handle 3D data (Z, Y, X) -> Take max projection or specific level?
                    # README says: "NetCDF Original (500x500) -> AveragePooling2D -> Tensor (250x250)"
                    # But here we assume data might already be preprocessed or we do it here.
                    # For simplicity, let's assume we take the max over Z if 3D, or it's already 2D.
                    
                    if data.ndim == 3:
                        data = np.nanmax(data, axis=0) # Max projection
                    
                    # Normalization
                    data = np.nan_to_num(data, nan=self.min_dbz)
                    data = np.clip(data, self.min_dbz, self.max_dbz)
                    data = (data - self.min_dbz) / (self.max_dbz - self.min_dbz)
                    
                    # Convert to tensor (C, H, W)
                    tensor = torch.from_numpy(data).float()
                    if tensor.ndim == 2:
                        tensor = tensor.unsqueeze(0)
                        
                    # Resize if necessary
                    if tensor.shape[1] != self.img_height or tensor.shape[2] != self.img_width:
                        # interpolate expects (B, C, H, W)
                        tensor = torch.nn.functional.interpolate(
                            tensor.unsqueeze(0), 
                            size=(self.img_height, self.img_width), 
                            mode='bilinear', 
                            align_corners=False
                        ).squeeze(0)
                    
                    frames.append(tensor)
            except Exception as e:
                logger.error(f"Error loading {p}: {e}")
                # Return zero tensor in case of error to avoid crashing
                return torch.zeros((self.input_steps + self.prediction_steps, 1, self.img_height, self.img_width))

        # Stack frames: (Seq, C, H, W)
        # Note: frames are already (C, H, W) tensors
        frames = torch.stack(frames, dim=0)
        
        # Split into input and target
        input_seq = frames[:self.input_steps]
        target_seq = frames[self.input_steps:]
        
        return input_seq, target_seq

# --- Training Function ---
def train(config_path, resume_from=None):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    # Hyperparameters
    lr = float(config['training']['lr'])
    epochs = config['training']['epochs']
    save_dir = config['training']['save_dir']
    os.makedirs(save_dir, exist_ok=True)
    
    # Dataset
    dataset = StormDataset(
        data_dir=config['data']['data_dir'],
        input_steps=config['data']['input_steps'],
        prediction_steps=config['data']['prediction_steps'],
        img_height=config['data']['img_height'],
        img_width=config['data']['img_width'],
        min_dbz=config['data']['min_dbz'],
        max_dbz=config['data']['max_dbz']
    )
    
    dataloader = DataLoader(
        dataset, 
        batch_size=config['data']['batch_size'], 
        shuffle=True, 
        num_workers=config['data']['num_workers'],
        pin_memory=True
    )
    
    # Model
    model = ConvLSTM3D_Enhanced(
        input_dim=config['model']['input_dim'],
        hidden_dims=config['model']['hidden_dims'],
        kernel_sizes=config['model']['kernel_sizes'],
        num_layers=config['model']['num_layers'],
        pred_steps=config['data']['prediction_steps'],
        use_layer_norm=config['model']['use_layer_norm'],
        img_height=config['data']['img_height'],
        img_width=config['data']['img_width']
    ).to(device)
    
    # Optimizer & Scheduler
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=float(config['training']['weight_decay']))
    
    start_epoch = 0
    
    # Resume
    resume_path = resume_from or config['training']['resume_from']
    if resume_path and os.path.exists(resume_path):
        logger.info(f"Resuming from {resume_path}")
        checkpoint = torch.load(resume_path, map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        start_epoch = checkpoint['epoch'] + 1
        logger.info(f"Resumed from epoch {start_epoch}")
    
    # Loss
    criterion = CombinedLoss(
        high_penalty_weight=config['loss']['high_penalty_weight'],
        ssim_weight=config['loss']['ssim_weight'],
        high_threshold=config['loss']['high_threshold']
    ).to(device)
    
    # Scheduler
    scheduler_type = config['training'].get('scheduler', 'plateau')
    if scheduler_type == 'plateau':
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=config['training'].get('patience', 4), factor=0.5, verbose=True)
    elif scheduler_type == 'cosine':
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    else:
        scheduler = None

    scaler = GradScaler()
    
    # Loop
    for epoch in range(start_epoch, start_epoch + epochs):
        model.train()
        epoch_loss = 0.0
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{start_epoch + epochs}")
        
        for inputs, targets in pbar:
            inputs = inputs.to(device)
            targets = targets.to(device)
            
            optimizer.zero_grad()
            
            with autocast():
                outputs = model(inputs)
                # Ensure outputs match targets shape if necessary
                # Model output: (B, PredSteps, C, H, W)
                # Targets: (B, PredSteps, C, H, W)
                loss, loss_components = criterion(outputs, targets)
            
            scaler.scale(loss).backward()
            
            # Gradient Clipping
            if 'gradient_clip' in config['training']:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), config['training']['gradient_clip'])
            
            scaler.step(optimizer)
            scaler.update()
            
            epoch_loss += loss.item()
            pbar.set_postfix({"loss": loss.item(), "ssim": loss_components['ssim']})
        
        avg_loss = epoch_loss / len(dataloader)
        logger.info(f"Epoch {epoch+1} Complete. Avg Loss: {avg_loss:.6f}")
        
        if scheduler:
            if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(avg_loss)
            else:
                scheduler.step()
        
        # Save Checkpoint
        checkpoint_path = os.path.join(save_dir, f"{config['experiment_name']}_epoch_{epoch+1}.pth")
        best_path = os.path.join(save_dir, f"{config['experiment_name']}_best.pth")
        
        save_dict = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'loss': avg_loss,
            'config': config
        }
        
        torch.save(save_dict, checkpoint_path)
        # Simple logic: just overwrite best for now, or implement comparison
        torch.save(save_dict, best_path)
        logger.info(f"Saved checkpoint to {checkpoint_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, required=True, help='Path to config file')
    parser.add_argument('--resume_from', type=str, default=None, help='Path to checkpoint to resume from')
    args = parser.parse_args()
    
    train(args.config, args.resume_from)

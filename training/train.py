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
        
        # Create valid sequences respecting folder boundaries
        self.sequences = []
        total_files = 0
        total_len = input_steps + prediction_steps
        
        # Walk through directories to find sequences
        # This guarantees we NEVER mix files from different folders
        for root, _, files in os.walk(data_dir):
            nc_files = sorted([f for f in files if f.endswith('.nc')])
            if not nc_files: continue
            
            total_files += len(nc_files)
            file_paths = [os.path.join(root, f) for f in nc_files]
            
            # Apply sliding window per folder
            if len(file_paths) >= total_len:
                for i in range(len(file_paths) - total_len + 1):
                    self.sequences.append(file_paths[i : i + total_len])
            
        logger.info(f"Scanned directories. Found {total_files} files. Created {len(self.sequences)} sequences.")

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
                    data = torch.from_numpy(data).float()
                    
                    # Robust Dimension Reduction: Goal is (H, W) or (C, H, W)
                    # Loop until we have 2 or 3 dims. 
                    # If we have (T, L, H, W) -> Squeeze T=1, MaxPool L
                    while data.ndim > 2:
                        # If first dim is 1 (e.g. Time=1), squeeze it
                        if data.shape[0] == 1:
                            data = data.squeeze(0)
                        else:
                            # If first dim > 1 (e.g. Levels=18), Max Projection
                            data = torch.max(data, dim=0)[0]
                    
                    # Now data should be (H, W)
                    if data.ndim == 2:
                        data = data.unsqueeze(0) # (1, H, W)
                        
                    # Resize if necessary
                    if data.shape[1] != self.img_height or data.shape[2] != self.img_width:
                        # interpolate expects (B, C, H, W) -> (1, 1, H, W)
                        data = torch.nn.functional.interpolate(
                            data.unsqueeze(0), 
                            size=(self.img_height, self.img_width), 
                            mode='bilinear', 
                            align_corners=False
                        ).squeeze(0)
                    
                    # Log shape for debug if needed (only once)
                    # if idx == 0 and len(frames) == 0:
                    #     print(f"DEBUG: Frame shape after processing: {data.shape}")

                    frames.append(data)
            except Exception as e:
                logger.error(f"Error loading {p}: {e}")
                # Return tuple of zero tensors to allow unpacking
                # Shape: (Seq, C, H, W)
                input_seq = torch.zeros((self.input_steps, 1, self.img_height, self.img_width))
                target_seq = torch.zeros((self.prediction_steps, 1, self.img_height, self.img_width))
                return input_seq, target_seq

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
    elif scheduler_type == 'warmup':
        # Linear Warmup: Start at 10% of LR and increase linearly for 5 epochs, then constant
        scheduler = optim.lr_scheduler.LinearLR(optimizer, start_factor=0.1, total_iters=5)
    else:
        scheduler = None

    scaler = GradScaler()
    
    # CUDNN Stability for H200
    torch.backends.cudnn.benchmark = False
    
    # Loop
    for epoch in range(start_epoch, start_epoch + epochs):
        model.train()
        epoch_loss = 0.0
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{start_epoch + epochs}")
        
        for inputs, targets in pbar:
            inputs = inputs.to(device)
            targets = targets.to(device)
            
            optimizer.zero_grad()
            
            # Debug: Check for NaNs in input
            if torch.isnan(inputs).any() or torch.isnan(targets).any():
                logger.error(f"NaN detected in inputs/targets at epoch {epoch}")
                continue

            # Forward (Full Precision - No AMP)
            outputs = model(inputs)
            loss, loss_dict = criterion(outputs, targets)
            
            if torch.isnan(loss):
                logger.error(f"NaN Loss detected at epoch {epoch}. Components: {loss_dict}")
                # Optional: continue or break. For now let's just log and skip step to avoid wrecking weights
                optimizer.zero_grad()
                continue

            # Backward
            loss.backward()
            
            # Clip
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(config['training']['gradient_clip']))
            
            # Step
            optimizer.step()
            # scaler is removed
            
            epoch_loss += loss.item()
            
            # Update pbar
            pbar.set_postfix({
                'loss': loss.item(), 
                'mse': loss_dict['mse'], 
                'ssim': loss_dict['ssim']
            })
            
        # Scheduler Step (After Optimizer Step)
        if scheduler is not None:
            # If Plateau, needs metric
            if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(epoch_loss / len(dataloader))
            else:
                scheduler.step()
                
        avg_loss = epoch_loss / len(dataloader)
        logger.info(f"Epoch {epoch+1} Complete. Avg Loss: {avg_loss:.4f}")
        
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
        
        # --- Cleanup Strategy: Keep only 'best' and 'latest' to save space ---
        # User requested to delete models from 1 to 9 if we are at 10.
        try:
            # Find all checkpoints for this experiment (excluding 'best')
            chk_pattern = os.path.join(save_dir, f"{config['experiment_name']}_epoch_*.pth")
            all_checkpoints = sorted(glob.glob(chk_pattern))
            
            # If we have more than 1 checkpoint, keep only the last one (current)
            # The 'best' file is separate, so we don't need to worry about deleting it here.
            for chk in all_checkpoints[:-1]:
                os.remove(chk)
                logger.info(f"Deleted old checkpoint: {chk}")
        except Exception as e:
            logger.warning(f"Error deleting old checkpoints: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, required=True, help='Path to config file')
    parser.add_argument('--resume_from', type=str, default=None, help='Path to checkpoint to resume from')
    args = parser.parse_args()
    
    train(args.config, args.resume_from)

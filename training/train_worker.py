
import os
import glob
import random
import time
import logging
import subprocess
from datetime import datetime, timedelta

import xarray as xr
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.utils.checkpoint import checkpoint
import torchmetrics
import matplotlib.pyplot as plt

# ==============================================================================
# CONFIGURACIÓN DEL SCRIPT
# ==============================================================================

# Mover la configuración a un diccionario global para fácil acceso y modificación.
CONFIG = {
    # --- Rutas dentro del contenedor Docker ---
    'dataset_root_dir': "/app/datasets",
    'model_save_dir': "/app/model_output",
    'predictions_output_dir': "/app/predictions_output",

    # --- Parámetros del Dataset y Descarga ---
    'dataset_gdown_id': '1UFm8S6-Zu-YI6a_z_vUnGSqGz00ClChH', # ID del archivo a descargar
    'dataset_archive_name': 'sample.tar.gz',
    'dataset_unpacked_name': 'sample', # Nombre de la carpeta una vez descomprimida

    # --- Parámetros de Pre-procesamiento y Secuencia ---
    'downsample_size': (250, 250), # (height, width) para el downsampling
    'seq_len': 18,
    'pred_len': 7,
    'seq_stride': 5, # Stride para las ventanas deslizantes (ajustar para más o menos solapamiento)

    # --- Parámetros de División del Dataset ---
    'train_val_split_ratio': 0.8,

    # --- Parámetros de Normalización y Físicos ---
    'min_dbz_norm': -29.0,
    'max_dbz_norm': 65.0,
    
    # --- Parámetros del Modelo ---
    'model_input_dim': 1,
    'model_hidden_dims': [128, 128, 128],
    'model_kernel_sizes': [(3, 3), (3, 3), (3, 3)],
    'model_num_layers': 3,
    'model_use_layer_norm': True,

    # --- Parámetros de Entrenamiento ---
    'batch_size': 2, # Ajustar según VRAM
    'epochs': 50,
    'learning_rate': 1e-5,
    'weight_decay': 1e-5,
    'lr_patience': 3,
    'use_amp': True, # Automatic Mixed Precision
    'clip_grad_norm': 1.0,
    'accumulation_steps': 4, # Gradiente acumulado

    # --- Parámetros de la Función de Pérdida ---
    'use_ssim_loss': True,
    'ssim_loss_weight': 0.5,
    'high_dbz_threshold_norm': 0.4, # Umbral para píxeles importantes
    'high_penalty_weight': 10.0,

    # --- Parámetros de Logging y Checkpoints ---
    'log_interval': 10, # Cada cuántos batches loggear
    'checkpoint_interval': 1, # Cada cuántas épocas guardar checkpoint
    'seed': 42
}

# Configuración del Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# CLASES Y FUNCIONES (Adaptadas del Notebook)
# ==============================================================================

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = False
        torch.backends.cudnn.benchmark = True
    logging.info(f"Semillas configuradas con valor: {seed}")

class RadarDataset(Dataset):
    def __init__(self, sequence_paths, config):
        self.sequence_paths = sequence_paths
        self.config = config
        self.seq_len = config['seq_len']
        self.total_seq_len = config['seq_len'] + config['pred_len']
        self.downsample_size = config['downsample_size']
        logging.info(f"RadarDataset inicializado con {len(self.sequence_paths)} secuencias.")

    def __len__(self):
        return len(self.sequence_paths)

    def __getitem__(self, idx):
        sequence_files = self.sequence_paths[idx]
        data_list = []

        for file_path in sequence_files:
            try:
                with xr.open_dataset(file_path, mask_and_scale=True, decode_times=False) as ds:
                    # Downsampling usando xarray
                    resampled_ds = ds.interp(y=np.linspace(ds.y.min(), ds.y.max(), self.downsample_size[0]),
                                             x=np.linspace(ds.x.min(), ds.x.max(), self.downsample_size[1]),
                                             method="linear")
                    dbz_physical = resampled_ds['DBZ'].values

                dbz_clipped = np.clip(dbz_physical, self.config['min_dbz_norm'], self.config['max_dbz_norm'])
                dbz_normalized = (dbz_clipped - self.config['min_dbz_norm']) / (self.config['max_dbz_norm'] - self.config['min_dbz_norm'])
                data_list.append(dbz_normalized[0, ..., np.newaxis])

            except Exception as e:
                logging.error(f"Error procesando {file_path}. Omitiendo. Error: {e}")
                return self.__getitem__((idx + 1) % len(self))
        
        full_sequence = np.stack(data_list, axis=1)
        
        input_tensor = full_sequence[:, :self.seq_len, ...]
        output_tensor = full_sequence[:, self.seq_len:, ...]

        x = torch.from_numpy(np.nan_to_num(input_tensor, nan=0.0)).float()
        y = torch.from_numpy(output_tensor).float()
        
        return x, y

class ConvLSTMCell(nn.Module):
    def __init__(self, input_dim, hidden_dim, kernel_size, bias=True):
        super(ConvLSTMCell, self).__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.kernel_size = kernel_size
        self.padding = kernel_size[0] // 2, kernel_size[1] // 2
        self.bias = bias
        self.conv = nn.Conv2d(in_channels=self.input_dim + self.hidden_dim,
                              out_channels=4 * self.hidden_dim,
                              kernel_size=self.kernel_size,
                              padding=self.padding,
                              bias=self.bias)
        nn.init.xavier_uniform_(self.conv.weight)
        if self.bias:
            nn.init.zeros_(self.conv.bias)

    def forward(self, input_tensor, cur_state):
        h_cur, c_cur = cur_state
        combined = torch.cat([input_tensor, h_cur], dim=1)
        combined_conv = self.conv(combined)
        cc_i, cc_f, cc_o, cc_g = torch.split(combined_conv, self.hidden_dim, dim=1)
        i = torch.sigmoid(cc_i)
        f = torch.sigmoid(cc_f)
        o = torch.sigmoid(cc_o)
        g = torch.tanh(cc_g)
        c_next = f * c_cur + i * g
        h_next = o * torch.tanh(c_next)
        return h_next, c_next

    def init_hidden(self, batch_size, image_size, device):
        height, width = image_size
        return (torch.zeros(batch_size, self.hidden_dim, height, width, device=device),
                torch.zeros(batch_size, self.hidden_dim, height, width, device=device))

class ConvLSTM2DLayer(nn.Module):
    def __init__(self, input_dim, hidden_dim, kernel_size, use_layer_norm, img_size, return_all_layers=False):
        super(ConvLSTM2DLayer, self).__init__()
        self.cell = ConvLSTMCell(input_dim, hidden_dim, kernel_size)
        self.use_layer_norm = use_layer_norm
        self.return_all_layers = return_all_layers
        if self.use_layer_norm:
            self.layer_norm = nn.LayerNorm([hidden_dim, img_size[0], img_size[1]])

    def forward(self, input_tensor, hidden_state=None):
        b, seq_len, _, h, w = input_tensor.size()
        device = input_tensor.device
        if hidden_state is None:
            hidden_state = self.cell.init_hidden(b, (h, w), device)

        layer_output_list = []
        h_cur, c_cur = hidden_state
        for t in range(seq_len):
            h_cur, c_cur = self.cell(input_tensor=input_tensor[:, t, :, :, :], cur_state=[h_cur, c_cur])
            layer_output_list.append(h_cur)

        if self.return_all_layers:
            layer_output = torch.stack(layer_output_list, dim=1)
            if self.use_layer_norm:
                B_ln, T_ln, C_ln, H_ln, W_ln = layer_output.shape
                output_reshaped = layer_output.contiguous().view(B_ln * T_ln, C_ln, H_ln, W_ln)
                normalized_output = self.layer_norm(output_reshaped)
                layer_output = normalized_output.view(B_ln, T_ln, C_ln, H_ln, W_ln)
        else:
            layer_output = h_cur.unsqueeze(1)

        return layer_output, (h_cur, c_cur)

class Seq2Seq(nn.Module):
    def __init__(self, config):
        super(Seq2Seq, self).__init__()
        self.config = config
        self.num_layers = config['model_num_layers']
        self.hidden_dims = config['model_hidden_dims']
        
        self.layers = nn.ModuleList()
        current_dim = config['model_input_dim']
        for i in range(self.num_layers):
            is_last_layer = (i == self.num_layers - 1)
            self.layers.append(
                ConvLSTM2DLayer(
                    input_dim=current_dim,
                    hidden_dim=self.hidden_dims[i],
                    kernel_size=config['model_kernel_sizes'][i],
                    use_layer_norm=config['model_use_layer_norm'],
                    img_size=config['downsample_size'],
                    return_all_layers=not is_last_layer
                )
            )
            current_dim = self.hidden_dims[i]

        self.output_conv = nn.Conv3d(
            in_channels=self.hidden_dims[-1],
            out_channels=config['model_input_dim'] * config['pred_len'],
            kernel_size=(1, 3, 3),
            padding=(0, 1, 1)
        )
        self.sigmoid = nn.Sigmoid()
        nn.init.xavier_uniform_(self.output_conv.weight)
        nn.init.zeros_(self.output_conv.bias)
        logging.info(f"Modelo Seq2Seq creado: {self.num_layers} capas, Hidden dims: {self.hidden_dims}")

    def forward(self, x_volumetric):
        num_z_levels, b, seq_len, h, w, c_in = x_volumetric.shape
        all_level_predictions = []

        for z_idx in range(num_z_levels):
            current_input = x_volumetric[z_idx, ...].permute(0, 1, 4, 2, 3)
            hidden_states = [None] * self.num_layers

            for i in range(self.num_layers):
                layer_input = current_input
                # Usar checkpoint para ahorrar memoria
                layer_output, hidden_state = checkpoint(self.layers[i], layer_input, hidden_states[i], use_reentrant=False)
                hidden_states[i] = hidden_state
                current_input = layer_output

            output_for_conv3d = current_input.permute(0, 2, 1, 3, 4)
            raw_conv_output = self.output_conv(output_for_conv3d)
            
            pred_features = raw_conv_output.squeeze(2)
            level_pred = pred_features.view(b, self.config['pred_len'], self.config['model_input_dim'], h, w)
            level_pred = level_pred.permute(0, 1, 3, 4, 2)
            level_pred = self.sigmoid(level_pred)
            all_level_predictions.append(level_pred)

        return torch.stack(all_level_predictions, dim=0)

class SSIMLoss(nn.Module):
    def __init__(self, data_range=1.0, kernel_size=7):
        super(SSIMLoss, self).__init__()
        self.ssim_metric = torchmetrics.StructuralSimilarityIndexMeasure(
            data_range=data_range,
            kernel_size=kernel_size,
            reduction='elementwise_mean'
        ).to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))

    def forward(self, img1, img2):
        num_z, batch_s, pred_t, h, w, c = img1.shape
        img1_reshaped = img1.permute(0, 1, 2, 5, 3, 4).contiguous().view(-1, c, h, w)
        img2_reshaped = img2.permute(0, 1, 2, 5, 3, 4).contiguous().view(-1, c, h, w)
        ssim_val = self.ssim_metric(img1_reshaped, img2_reshaped)
        return 1.0 - ssim_val

def prepare_and_split_data(config):
    root_dir = os.path.join(config['dataset_root_dir'], config['dataset_unpacked_name'])
    if not os.path.exists(root_dir):
        logging.error(f"El directorio del dataset no fue encontrado en: {root_dir}")
        return [], []

    all_event_dirs = sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])
    if not all_event_dirs:
        logging.warning(f"No se encontraron directorios de eventos en {root_dir}")
        return [], []

    logging.info(f"Encontrados {len(all_event_dirs)} directorios de eventos.")
    split_idx = int(len(all_event_dirs) * config['train_val_split_ratio'])
    train_dirs = all_event_dirs[:split_idx]
    val_dirs = all_event_dirs[split_idx:]
    logging.info(f"División de eventos - Entrenamiento: {len(train_dirs)}, Validación: {len(val_dirs)}")

    def create_sliding_windows(event_dirs, base_path):
        sequences = []
        total_seq_len = config['seq_len'] + config['pred_len']
        for event_dir in event_dirs:
            files = sorted(glob.glob(os.path.join(base_path, event_dir, "*.nc")))
            if len(files) >= total_seq_len:
                for i in range(0, len(files) - total_seq_len + 1, config['seq_stride']):
                    sequences.append(files[i : i + total_seq_len])
        return sequences

    train_sequences = create_sliding_windows(train_dirs, root_dir)
    val_sequences = create_sliding_windows(val_dirs, root_dir)
    logging.info(f"Generadas {len(train_sequences)} secuencias de entrenamiento y {len(val_sequences)} de validación.")
    return train_sequences, val_sequences

def train_model(model, train_loader, val_loader, config):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=config['learning_rate'], weight_decay=config['weight_decay'])
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', factor=0.5, patience=config['lr_patience'], verbose=True)
    
    criterion_huber = nn.HuberLoss(reduction='none').to(device)
    criterion_ssim = SSIMLoss().to(device) if config['use_ssim_loss'] else None
    
    scaler = torch.amp.GradScaler(enabled=config['use_amp'])
    best_val_loss = float('inf')
    
    logging.info(f"Iniciando entrenamiento por {config['epochs']} épocas...")

    for epoch in range(config['epochs']):
        model.train()
        running_train_loss = 0.0
        optimizer.zero_grad()

        for batch_idx, (x, y) in enumerate(train_loader):
            x = x.to(device).permute(1, 0, 2, 3, 4, 5)
            y = y.to(device).permute(1, 0, 2, 3, 4, 5)

            with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=config['use_amp']):
                predictions = model(x)
                if predictions.shape != y.shape: continue

                valid_mask = ~torch.isnan(y)
                weights = torch.ones_like(y[valid_mask])
                weights[y[valid_mask] > config['high_dbz_threshold_norm']] = config['high_penalty_weight']
                
                pixel_wise_loss = criterion_huber(predictions[valid_mask], y[valid_mask])
                loss_huber = (pixel_wise_loss * weights).mean()
                
                current_loss = loss_huber
                if criterion_ssim:
                    preds_no_nan = torch.nan_to_num(predictions, nan=0.0)
                    y_no_nan = torch.nan_to_num(y, nan=0.0)
                    loss_ssim_val = criterion_ssim(preds_no_nan, y_no_nan)
                    current_loss = (1.0 - config['ssim_loss_weight']) * loss_huber + config['ssim_loss_weight'] * loss_ssim_val

                loss_to_accumulate = current_loss / config['accumulation_steps']

            scaler.scale(loss_to_accumulate).backward()

            if (batch_idx + 1) % config['accumulation_steps'] == 0:
                if config['clip_grad_norm']:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=config['clip_grad_norm'])
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()

            running_train_loss += current_loss.item()
            if (batch_idx + 1) % config['log_interval'] == 0:
                logging.info(f"Época {epoch+1}/{config['epochs']} [{batch_idx+1}/{len(train_loader)}] - Pérdida (batch): {current_loss.item():.6f}")

        avg_train_loss = running_train_loss / len(train_loader)
        
        # Validation
        model.eval()
        running_val_loss = 0.0
        with torch.no_grad():
            for x_val, y_val in val_loader:
                x_val = x_val.to(device).permute(1, 0, 2, 3, 4, 5)
                y_val = y_val.to(device).permute(1, 0, 2, 3, 4, 5)
                with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=config['use_amp']):
                    # Misma lógica de pérdida que en entrenamiento
                    predictions_val = model(x_val)
                    valid_mask_val = ~torch.isnan(y_val)
                    weights_val = torch.ones_like(y_val[valid_mask_val])
                    weights_val[y_val[valid_mask_val] > config['high_dbz_threshold_norm']] = config['high_penalty_weight']
                    pixel_wise_loss_val = criterion_huber(predictions_val[valid_mask_val], y_val[valid_mask_val])
                    val_loss_huber = (pixel_wise_loss_val * weights_val).mean()
                    
                    val_loss = val_loss_huber
                    if criterion_ssim:
                        preds_val_no_nan = torch.nan_to_num(predictions_val, nan=0.0)
                        y_val_no_nan = torch.nan_to_num(y_val, nan=0.0)
                        val_loss_ssim = criterion_ssim(preds_val_no_nan, y_val_no_nan)
                        val_loss = (1.0 - config['ssim_loss_weight']) * val_loss_huber + config['ssim_loss_weight'] * val_loss_ssim
                running_val_loss += val_loss.item()
        
        avg_val_loss = running_val_loss / len(val_loader)
        scheduler.step(avg_val_loss)
        logging.info(f"Época {epoch+1} completada. Pérdida (train): {avg_train_loss:.6f}, Pérdida (val): {avg_val_loss:.6f}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save({'epoch': epoch + 1, 'model_state_dict': model.state_dict()}, os.path.join(config['model_save_dir'], "best_model.pth"))
            logging.info(f"Mejor modelo guardado (Pérdida Val: {best_val_loss:.6f})")

        if (epoch + 1) % config['checkpoint_interval'] == 0:
            torch.save({'epoch': epoch + 1, 'model_state_dict': model.state_dict()}, os.path.join(config['model_save_dir'], f"checkpoint_epoch_{epoch+1}.pth"))
            logging.info(f"Checkpoint guardado en la época {epoch+1}")

def setup_dataset(config):
    """Descarga y descomprime el dataset si no existe."""
    dataset_path = os.path.join(config['dataset_root_dir'], config['dataset_unpacked_name'])
    archive_path = os.path.join(config['dataset_root_dir'], config['dataset_archive_name'])
    
    if os.path.exists(dataset_path):
        logging.info(f"El directorio del dataset ya existe en {dataset_path}. Saltando descarga.")
        return

    os.makedirs(config['dataset_root_dir'], exist_ok=True)
    
    # Descargar
    logging.info(f"Descargando dataset desde Google Drive (ID: {config['dataset_gdown_id']})...")
    try:
        subprocess.run(['gdown', '--id', config['dataset_gdown_id'], '-O', archive_path], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logging.error(f"Fallo la descarga con gdown. Asegúrate de que gdown esté instalado y el ID sea correcto. Error: {e}")
        return

    # Descomprimir
    logging.info(f"Descomprimiendo {archive_path}...")
    try:
        # Usar pigz para descompresión paralela
        subprocess.run(f"tar -I pigz -xf {archive_path} -C {config['dataset_root_dir']}", shell=True, check=True)
        logging.info("Descompresión completada.")
        os.remove(archive_path) # Limpiar el archivo comprimido
    except subprocess.CalledProcessError as e:
        logging.error(f"Fallo la descompresión. Error: {e}")

def main():
    """Función principal que orquesta el pipeline de entrenamiento."""
    set_seed(CONFIG['seed'])
    
    # Crear directorios de salida
    os.makedirs(CONFIG['model_save_dir'], exist_ok=True)
    os.makedirs(CONFIG['predictions_output_dir'], exist_ok=True)

    # 1. Preparar el dataset (descargar/descomprimir si es necesario)
    setup_dataset(CONFIG)

    # 2. Preparar y dividir los datos
    train_paths, val_paths = prepare_and_split_data(CONFIG)
    if not train_paths:
        logging.error("No se encontraron datos de entrenamiento. Abortando.")
        return

    # 3. Crear Datasets y DataLoaders
    train_dataset = RadarDataset(train_paths, CONFIG)
    val_dataset = RadarDataset(val_paths, CONFIG)
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=CONFIG['batch_size'], shuffle=False, num_workers=4, pin_memory=True)

    # 4. Inicializar el modelo
    model = Seq2Seq(CONFIG)
    logging.info(f"Arquitectura del modelo:\n{model}")
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logging.info(f"Número total de parámetros entrenables: {total_params:,}")

    # 5. Entrenar el modelo
    train_model(model, train_loader, val_loader, CONFIG)

    logging.info("Pipeline de entrenamiento completado.")

if __name__ == '__main__':
    main()

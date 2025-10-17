
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

    #Dataset de ejemplo pequeño para pruebas rápidas
    #https://drive.google.com/file/d/12-Ry9JtHpkBsjXWiWFqR-bPFlBNYCdjw/view?usp=sharing

    # --- Parámetros del Dataset y Descarga ---
    'dataset_gdown_id': '12-Ry9JtHpkBsjXWiWFqR-bPFlBNYCdjw', # ID del archivo a descargar
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
    'use_attention': True,

    # --- Parámetros de Entrenamiento ---
    'batch_size': 4, # Ajustar según VRAM
    'epochs': 5,
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
    'log_interval': 1, # Cada cuántos batches loggear
    'checkpoint_interval': 1, # Cada cuántas épocas guardar checkpoint
    'resume_checkpoint_path': None, # Ruta a un checkpoint para reanudar, ej: '/app/model_output/best_model.pth'
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
                    resampled_ds = ds.interp(y0=np.linspace(ds.y0.min(), ds.y0.max(), self.downsample_size[0]),
                                             x0=np.linspace(ds.x0.min(), ds.x0.max(), self.downsample_size[1]),
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

from backend.model.architecture import Seq2Seq

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

    # Obtiene todas las carpetas de secuencias que el usuario creó
    all_sequence_dirs = sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])
    if not all_sequence_dirs:
        logging.warning(f"No se encontraron directorios de secuencias en {root_dir}")
        return [], []

    logging.info(f"Encontrados {len(all_sequence_dirs)} directorios de secuencias.")
    
    # Mezclar las secuencias antes de dividirlas para asegurar que la validación sea una muestra representativa
    random.shuffle(all_sequence_dirs)

    # Dividir la lista de directorios de secuencias
    split_idx = int(len(all_sequence_dirs) * config['train_val_split_ratio'])
    train_dirs = all_sequence_dirs[:split_idx]
    val_dirs = all_sequence_dirs[split_idx:]
    logging.info(f"División de secuencias - Entrenamiento: {len(train_dirs)}, Validación: {len(val_dirs)}")

    # Nueva función simplificada para cargar las secuencias desde los directorios
    def load_sequences_from_dirs(sequence_dirs, base_path):
        sequences = []
        # La longitud esperada es la suma de la secuencia de entrada y la de predicción
        expected_len = config['seq_len'] + config['pred_len']
        for seq_dir in sequence_dirs:
            dir_path = os.path.join(base_path, seq_dir)
            files = sorted(glob.glob(os.path.join(dir_path, "*.nc")))
            
            # Verificar si el directorio contiene el número exacto de archivos
            if len(files) == expected_len:
                sequences.append(files)
            else:
                logging.warning(f"Omitiendo directorio {dir_path}: no contiene los {expected_len} archivos esperados. Encontrados: {len(files)}")
        return sequences

    train_sequences = load_sequences_from_dirs(train_dirs, root_dir)
    val_sequences = load_sequences_from_dirs(val_dirs, root_dir)
    
    logging.info(f"Cargadas {len(train_sequences)} secuencias de entrenamiento y {len(val_sequences)} de validación.")
    return train_sequences, val_sequences

def train_model(model, optimizer, scheduler, train_loader, val_loader, config, start_epoch=0):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    criterion_huber = nn.HuberLoss(reduction='none').to(device)
    criterion_ssim = SSIMLoss().to(device) if config['use_ssim_loss'] else None
    
    scaler = torch.amp.GradScaler(enabled=config['use_amp'])
    best_val_loss = float('inf')
    
    # Cargar best_val_loss si se reanuda
    if start_epoch > 0 and os.path.exists(os.path.join(config['model_save_dir'], "best_model.pth")):
        checkpoint = torch.load(os.path.join(config['model_save_dir'], "best_model.pth"))
        if 'best_val_loss' in checkpoint:
            best_val_loss = checkpoint['best_val_loss']
            logging.info(f"Reanudando con mejor pérdida de validación: {best_val_loss:.6f}")

    logging.info(f"Iniciando entrenamiento desde la época {start_epoch + 1} hasta la {config['epochs']}...")

    for epoch in range(start_epoch, config['epochs']):
        model.train()
        running_train_loss = 0.0
        running_train_ssim = 0.0
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
                    running_train_ssim += (1.0 - loss_ssim_val.item())
                else:
                    running_train_ssim += 0

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
                log_line = f"Época {epoch+1}/{config['epochs']} [{batch_idx+1}/{len(train_loader)}] - Pérdida (batch): {current_loss.item():.6f}"
                if config['use_ssim_loss'] and 'loss_ssim_val' in locals():
                    ssim_score = 1.0 - loss_ssim_val.item()
                    log_line += f", SSIM (batch): {ssim_score:.4f}"
                logging.info(log_line)

        avg_train_loss = running_train_loss / len(train_loader)
        avg_train_ssim = running_train_ssim / len(train_loader)
        
        # Validation
        model.eval()
        running_val_loss = 0.0
        running_val_ssim = 0.0
        with torch.no_grad():
            for x_val, y_val in val_loader:
                x_val = x_val.to(device).permute(1, 0, 2, 3, 4, 5)
                y_val = y_val.to(device).permute(1, 0, 2, 3, 4, 5)
                with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=config['use_amp']):
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
                        running_val_ssim += (1.0 - val_loss_ssim.item())
                    else:
                        running_val_ssim += 0
                running_val_loss += val_loss.item()
        
        avg_val_loss = running_val_loss / len(val_loader)
        avg_val_ssim = running_val_ssim / len(val_loader)
        scheduler.step(avg_val_loss)
        
        log_msg = f"Época {epoch+1} completada. Pérdida (train): {avg_train_loss:.6f}, Pérdida (val): {avg_val_loss:.6f}"
        if config['use_ssim_loss']:
            log_msg += f", SSIM (train): {avg_train_ssim:.4f}, SSIM (val): {avg_val_ssim:.4f}"
        logging.info(log_msg)

        # Guardar checkpoint de estado completo
        def save_checkpoint(path, is_best=False):
            state = {
                'epoch': epoch + 1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'best_val_loss': best_val_loss if is_best else avg_val_loss,
            }
            torch.save(state, path)

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            save_checkpoint(os.path.join(config['model_save_dir'], "best_model.pth"), is_best=True)
            logging.info(f"Mejor modelo guardado (Pérdida Val: {best_val_loss:.6f})")

        if (epoch + 1) % config['checkpoint_interval'] == 0:
            save_checkpoint(os.path.join(config['model_save_dir'], f"checkpoint_epoch_{epoch+1}.pth"))
            logging.info(f"Checkpoint guardado en la época {epoch+1}")

def generate_predictions(config):
    logging.info("Iniciando generación de predicciones post-entrenamiento...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 1. Cargar el mejor modelo
    model = Seq2Seq(config).to(device)
    best_model_path = os.path.join(config['model_save_dir'], 'best_model.pth')
    if not os.path.exists(best_model_path):
        logging.error("No se encontró el mejor modelo ('best_model.pth'). Abortando predicción.")
        return

    checkpoint = torch.load(best_model_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    logging.info("Mejor modelo cargado para predicción.")

    # 2. Preparar el dataloader de validación
    _, val_paths = prepare_and_split_data(config)
    if not val_paths:
        logging.error("No se encontraron datos de validación para generar predicciones.")
        return
    val_dataset = RadarDataset(val_paths, config)
    val_loader = DataLoader(val_dataset, batch_size=config['batch_size'], shuffle=False, num_workers=4, pin_memory=True)

    # 3. Iterar y guardar predicciones
    output_dir = config['predictions_output_dir']
    with torch.no_grad():
        for i, (x, y_true) in enumerate(val_loader):
            x = x.to(device).permute(1, 0, 2, 3, 4, 5)
            
            with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=config['use_amp']):
                predictions_norm = model(x)

            # Denormalizar
            min_dbz, max_dbz = config['min_dbz_norm'], config['max_dbz_norm']
            predictions_physical = predictions_norm.cpu().numpy() * (max_dbz - min_dbz) + min_dbz
            
            # Guardar cada secuencia del batch como un archivo .nc
            for j in range(predictions_physical.shape[1]): # Iterar sobre el tamaño del batch
                pred_seq = predictions_physical[:, j, :, :, :, 0] # Shape: (pred_len, H, W)
                
                # Crear DataArray de xarray
                da = xr.DataArray(
                    pred_seq,
                    dims=('time', 'y', 'x'),
                    coords={
                        'time': np.arange(pred_seq.shape[0]),
                        'y': np.arange(pred_seq.shape[1]),
                        'x': np.arange(pred_seq.shape[2])
                    },
                    attrs={
                        'description': 'Precipitation forecast (DBZ)',
                        'units': 'dBZ'
                    }
                )
                
                output_filename = os.path.join(output_dir, f'prediction_batch_{i}_seq_{j}.nc')
                da.to_netcdf(output_filename)

    logging.info(f"Predicciones guardadas en '{output_dir}'.")


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
    set_seed(CONFIG.get('seed', 42))
    
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

    # 4. Inicializar modelo, optimizador y scheduler
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = Seq2Seq(CONFIG).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG['learning_rate'], weight_decay=CONFIG['weight_decay'])
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', factor=0.5, patience=CONFIG['lr_patience'], verbose=True)
    
    start_epoch = 0
    # --- Lógica para reanudar entrenamiento ---
    if CONFIG.get('resume_checkpoint_path') and os.path.exists(CONFIG['resume_checkpoint_path']):
        try:
            logging.info(f"Cargando checkpoint desde: {CONFIG['resume_checkpoint_path']}")
            checkpoint = torch.load(CONFIG['resume_checkpoint_path'], map_location=device)
            
            model.load_state_dict(checkpoint['model_state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
            start_epoch = checkpoint['epoch']
            
            logging.info(f"Checkpoint cargado. Reanudando entrenamiento desde la época {start_epoch + 1}.")
        except Exception as e:
            logging.error(f"Error al cargar el checkpoint: {e}. Empezando entrenamiento desde cero.")
            start_epoch = 0 # Reset epoch
    else:
        if CONFIG.get('resume_checkpoint_path'):
            logging.warning(f"Archivo de checkpoint no encontrado en {CONFIG['resume_checkpoint_path']}. Empezando desde cero.")

    logging.info(f"Arquitectura del modelo:\n{model}")
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logging.info(f"Número total de parámetros entrenables: {total_params:,}")

    # 5. Entrenar el modelo
    train_model(model, optimizer, scheduler, train_loader, val_loader, CONFIG, start_epoch)

    # 6. Generar predicciones con el mejor modelo
    generate_predictions(CONFIG)

    logging.info("Pipeline de entrenamiento y predicción completado.")

if __name__ == '__main__':
    main()

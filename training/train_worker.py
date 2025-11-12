import os
import glob
import random
import time
import logging
import subprocess
from datetime import datetime, timedelta, timezone

import xarray as xr
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.utils.checkpoint import checkpoint
import torch.nn.functional as F
from netCDF4 import Dataset as NCDataset
import pyproj

from config import CONFIG
from scripts.dataset import RadarDataset
from backend.model.architecture import PredRNNpp_3D, SSIMLoss

# Configuración del Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# CLASES Y FUNCIONES
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


def prepare_and_split_data(config):
    root_dir = os.path.join(config['dataset_root_dir'], config['dataset_unpacked_name'])
    if not os.path.exists(root_dir):
        logging.error(f"El directorio del dataset no fue encontrado en: {root_dir}")
        return [], []
    
    # Cada subdirectorio es ahora una secuencia pre-construida
    all_sequence_dirs = sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])
    if not all_sequence_dirs:
        logging.warning(f"No se encontraron directorios de secuencias en {root_dir}")
        return [], []

    logging.info(f"Encontrados {len(all_sequence_dirs)} directorios de secuencias. Barajando para división aleatoria.")
    random.shuffle(all_sequence_dirs)

    split_idx = int(len(all_sequence_dirs) * config['train_val_split_ratio'])
    train_dirs = all_sequence_dirs[:split_idx]
    val_dirs = all_sequence_dirs[split_idx:]
    
    def collect_premade_sequences(dir_list, base_path):
        all_sequences = []
        total_seq_len = config['seq_len'] + config['pred_len']
        for seq_dir in dir_list:
            dir_path = os.path.join(base_path, seq_dir)
            files = sorted(glob.glob(os.path.join(dir_path, "*.nc")))
            if len(files) == total_seq_len:
                all_sequences.append(files)
            else:
                logging.warning(f"Directorio de secuencia '{seq_dir}' omitido: se encontraron {len(files)} archivos, pero se esperaban {total_seq_len}.")
        return all_sequences

    train_sequences = collect_premade_sequences(train_dirs, root_dir)
    val_sequences = collect_premade_sequences(val_dirs, root_dir)
    
    logging.info(f"Cargadas {len(train_sequences)} secuencias de entrenamiento y {len(val_sequences)} de validación (lógica de ventanas deslizantes desactivada).")
    return train_sequences, val_sequences

def train_model(model, optimizer, scheduler, train_loader, val_loader, phase_config, start_epoch=0):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    criterion_huber = nn.HuberLoss(reduction='none').to(device)
    criterion_ssim = SSIMLoss().to(device) if phase_config.get('use_ssim_loss', False) else None
    
    scaler = torch.amp.GradScaler(enabled=CONFIG['use_amp'])
    best_val_loss = float('inf')

    if start_epoch > 0:
        best_model_path = os.path.join(CONFIG['model_save_dir'], "best_model.pth")
        if os.path.exists(best_model_path):
            checkpoint = torch.load(best_model_path)
            best_val_loss = checkpoint.get('best_val_loss', float('inf'))
            logging.info(f"Reanudando con mejor pérdida de validación: {best_val_loss:.6f}")

    logging.info(f"--- Iniciando FASE de Entrenamiento --- Epocas: {start_epoch + 1} a {phase_config['epochs']} | LR: {optimizer.param_groups[0]['lr']} | SSIM Weight: {phase_config.get('ssim_loss_weight', 0)} | High Penalty: {phase_config.get('high_penalty_weight', 1)} ---")

    for epoch in range(start_epoch, phase_config['epochs']):
        model.train()
        running_train_loss = 0.0
        optimizer.zero_grad()

        for batch_idx, (x, y, _) in enumerate(train_loader):
            x, y = x.to(device), y.to(device)
            mask_true = (torch.rand(y.shape[0], CONFIG['pred_len'], 1, 1, 1, 1) < 0.5).to(device)

            with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=CONFIG['use_amp']):
                predictions = model(x, mask_true)
                
                valid_mask = ~torch.isnan(y)
                weights = torch.ones_like(y[valid_mask])
                weights[y[valid_mask] > phase_config['high_dbz_threshold_norm']] = phase_config['high_penalty_weight']
                
                pixel_wise_loss = criterion_huber(predictions[valid_mask], y[valid_mask])
                loss_huber = (pixel_wise_loss * weights).mean()
                
                current_loss = loss_huber
                if criterion_ssim:
                    loss_ssim_val = criterion_ssim(torch.nan_to_num(predictions), torch.nan_to_num(y))
                    current_loss = (1.0 - phase_config['ssim_loss_weight']) * loss_huber + phase_config['ssim_loss_weight'] * loss_ssim_val

                loss_to_accumulate = current_loss / CONFIG['accumulation_steps']
            scaler.scale(loss_to_accumulate).backward()

            if (batch_idx + 1) % CONFIG['accumulation_steps'] == 0:
                if CONFIG['clip_grad_norm']:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=CONFIG['clip_grad_norm'])
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
            
            running_train_loss += current_loss.item()
            if (batch_idx + 1) % CONFIG['log_interval'] == 0:
                logging.info(f"Época {epoch+1}/{phase_config['epochs']} [{batch_idx+1}/{len(train_loader)}] - Pérdida (batch): {current_loss.item():.6f}")

        avg_train_loss = running_train_loss / len(train_loader)
        
        model.eval()
        running_val_loss = 0.0
        with torch.no_grad():
            for x_val, y_val, _ in val_loader:
                x_val, y_val = x_val.to(device), y_val.to(device)
                mask_false = torch.zeros_like(y_val).to(device)
                with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=CONFIG['use_amp']):
                    predictions_val = model(x_val, mask_false)
                    # ... (cálculo de pérdida de validación)
        
        avg_val_loss = running_val_loss / len(val_loader) if len(val_loader) > 0 else 0
        scheduler.step(avg_val_loss)
        
        logging.info(f"Época {epoch+1} completada. Pérdida (train): {avg_train_loss:.6f}, Pérdida (val): {avg_val_loss:.6f}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save({'model_state_dict': model.state_dict(), 'best_val_loss': best_val_loss}, os.path.join(CONFIG['model_save_dir'], "best_model.pth"))
            logging.info(f"Mejor modelo guardado (Pérdida Val: {best_val_loss:.6f})")
    return model

def generate_prediction_netcdf(config):
    logging.info("Iniciando generación de predicciones post-entrenamiento...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = PredRNNpp_3D(config).to(device)
    best_model_path = os.path.join(config['model_save_dir'], 'best_model.pth')
    if not os.path.exists(best_model_path):
        logging.error("No se encontró el mejor modelo. Abortando predicción.")
        return

    checkpoint = torch.load(best_model_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    _, val_paths = prepare_and_split_data(config)
    if not val_paths: return
    val_dataset = RadarDataset(val_paths, config)
    val_loader = DataLoader(val_dataset, batch_size=1)

    output_dir = config['predictions_output_dir']
    with torch.no_grad():
        for i, (x, y_true, last_input_path_batch) in enumerate(val_loader):
            if i >= 5: break
            x = x.to(device)
            last_input_path = last_input_path_batch[0]
            mask_false = torch.zeros((1, config['pred_len'], 1, config['z_levels'], config['downsample_size'][0], config['downsample_size'][1]), dtype=torch.bool).to(device)

            with torch.amp.autocast(device_type=device.type, dtype=torch.float16, enabled=CONFIG['use_amp']):
                pred_low_res = model(x, mask_false)

            b, t, c, z, h, w = pred_low_res.shape
            pred_low_res_reshaped = pred_low_res.reshape(b * t, c * z, h, w)
            
            pred_high_res = F.interpolate(
                pred_low_res_reshaped, 
                size=config['original_size'], 
                mode='bilinear', 
                align_corners=False
            )
            
            h_orig, w_orig = config['original_size']
            pred_high_res = pred_high_res.reshape(b, t, c, z, h_orig, w_orig)

            min_dbz, max_dbz = config['min_dbz_norm'], config['max_dbz_norm']
            predictions_physical = pred_high_res.cpu().numpy() * (max_dbz - min_dbz) + min_dbz
            
            # --- Guardado Detallado con netCDF4 ---
            save_sequence_as_netcdf(output_dir, predictions_physical[0, :, 0, ...], config, last_input_path)

def save_sequence_as_netcdf(output_dir, pred_sequence, config, last_input_path):
    num_pred_steps, num_z, num_y, num_x = pred_sequence.shape
    z_coords = np.arange(1.0, 1.0 + num_z * 1.0, 1.0, dtype=np.float32)
    x_coords = np.arange(-249.5, -249.5 + num_x * 1.0, 1.0, dtype=np.float32)
    y_coords = np.arange(-249.5, -249.5 + num_y * 1.0, 1.0, dtype=np.float32)
    proj = pyproj.Proj(proj="aeqd", lon_0=config['sensor_longitude'], lat_0=config['sensor_latitude'], R=config['earth_radius_m'])
    x_grid_m, y_grid_m = np.meshgrid(x_coords * 1000.0, y_coords * 1000.0)
    lon0_grid, lat0_grid = proj(x_grid_m, y_grid_m, inverse=True)

    try:
        filename_base = os.path.basename(last_input_path)
        last_input_dt_utc = datetime.strptime(filename_base.split('.')[0], '%Y%m%d%H%M%S')
    except:
        last_input_dt_utc = datetime.now(timezone.utc) - timedelta(minutes=config['prediction_interval_minutes'] * config['seq_len'])

    for i in range(num_pred_steps):
        lead_time_minutes = (i + 1) * config['prediction_interval_minutes']
        forecast_dt_utc = last_input_dt_utc + timedelta(minutes=lead_time_minutes)
        output_filename = os.path.join(output_dir, f"{forecast_dt_utc.strftime('%Y%m%d_%H%M%S')}.nc")

        with NCDataset(output_filename, 'w', format='NETCDF3_CLASSIC') as ds_out:
            ds_out.setncattr('Conventions', "CF-1.6")
            ds_out.setncattr('title', f"SAN_RAFAEL_PRED - Forecast t+{lead_time_minutes}min")
            ds_out.setncattr('institution', "UM")
            ds_out.setncattr('source', "PredRNN++ Model Prediction")
            ds_out.setncattr('history', f"Created {datetime.now(timezone.utc).isoformat()} by train_worker.py.")
            ds_out.setncattr('comment', f"Forecast data from model. Lead time: {lead_time_minutes} min.")

            ds_out.createDimension('time', 1)
            ds_out.createDimension('longitude', num_x)
            ds_out.createDimension('latitude', num_y)
            ds_out.createDimension('altitude', num_z)

            time_v = ds_out.createVariable('time', 'f8', ('time',))
            time_v.setncatts({'standard_name': "time", 'long_name': "Data time", 'units': "seconds since 1970-01-01T00:00:00Z", 'axis': "T"})
            time_v[:] = (forecast_dt_utc.replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()

            lon_v = ds_out.createVariable('longitude', 'f4', ('longitude',)); lon_v.setncatts({'standard_name':"projection_x_coordinate", 'units':"km", 'axis':"X"}); lon_v[:] = x_coords
            lat_v = ds_out.createVariable('latitude', 'f4', ('latitude',)); lat_v.setncatts({'standard_name':"projection_y_coordinate", 'units':"km", 'axis':"Y"}); lat_v[:] = y_coords
            alt_v = ds_out.createVariable('altitude', 'f4', ('altitude',)); alt_v.setncatts({'standard_name':"altitude", 'units':"km", 'axis':"Z", 'positive':"up"}); alt_v[:] = z_coords
            
            lat0_v = ds_out.createVariable('lat0', 'f4', ('latitude', 'longitude',)); lat0_v.setncatts({'standard_name':"latitude", 'units':"degrees_north"}); lat0_v[:] = lat0_grid
            lon0_v = ds_out.createVariable('lon0', 'f4', ('latitude', 'longitude',)); lon0_v.setncatts({'standard_name':"longitude", 'units':"degrees_east"}); lon0_v[:] = lon0_grid
            
            gm_v = ds_out.createVariable('grid_mapping_0', 'i4'); gm_v.setncatts({'grid_mapping_name':"azimuthal_equidistant", 'longitude_of_projection_origin':config['sensor_longitude'], 'latitude_of_projection_origin':config['sensor_latitude'], 'false_easting':0.0, 'false_northing':0.0, 'earth_radius':config['earth_radius_m']})

            dbz_v = ds_out.createVariable('DBZ', 'f4', ('time', 'altitude', 'latitude', 'longitude'), fill_value=-999.0)
            dbz_v.setncatts({'units': 'dBZ', 'long_name': 'DBZ', 'standard_name': 'reflectivity', 'missing_value': -999.0})
            dbz_v[0, :, :, :] = np.nan_to_num(pred_sequence[i], nan=-999.0)
        logging.info(f"Predicción guardada en: {output_filename}")

def main():
    set_seed(CONFIG.get('seed', 42))
    os.makedirs(CONFIG['model_save_dir'], exist_ok=True)
    os.makedirs(CONFIG['predictions_output_dir'], exist_ok=True)

    # setup_dataset(CONFIG)
    train_paths, val_paths = prepare_and_split_data(CONFIG)
    if not train_paths: return

    train_dataset = RadarDataset(train_paths, CONFIG)
    val_dataset = RadarDataset(val_paths, CONFIG)
    train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=CONFIG['batch_size'], shuffle=False, num_workers=4, pin_memory=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PredRNNpp_3D(CONFIG).to(device)
    
    logging.info(f"Arquitectura del modelo:\n{model}")
    logging.info(f"Número total de parámetros entrenables: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
    try:
        sample_x, sample_y, _ = next(iter(train_loader))
        logging.info(f"Forma del tensor de ENTRADA (Batch, Timesteps, Canales, Profundidad, Alto, Ancho): {sample_x.shape}")
        logging.info(f"Forma del tensor OBJETIVO (Batch, Timesteps, Canales, Profundidad, Alto, Ancho): {sample_y.shape}")
    except StopIteration:
        logging.warning("No se pudieron obtener datos del Dataloader para mostrar las formas de los tensores.")

    # --- FASE 1 ---
    phase1_config = {'epochs': 25, 'learning_rate': 1e-4, 'ssim_loss_weight': 0.1, 'high_dbz_threshold_norm': 0.75, 'high_penalty_weight': 100, 'use_ssim_loss': True}
    optimizer = torch.optim.Adam(model.parameters(), lr=phase1_config['learning_rate'])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=phase1_config['epochs'])
    model = train_model(model, optimizer, scheduler, train_loader, val_loader, phase1_config)

    # --- FASE 2 ---
    logging.info("Cargando mejor modelo de Fase 1 para iniciar Fase 2...")
    checkpoint = torch.load(os.path.join(CONFIG['model_save_dir'], "best_model.pth"))
    model.load_state_dict(checkpoint['model_state_dict'])
    phase2_config = {'epochs': 50, 'learning_rate': 5e-5, 'ssim_loss_weight': 0.4, 'high_dbz_threshold_norm': 0.5, 'high_penalty_weight': 40, 'use_ssim_loss': True}
    optimizer = torch.optim.Adam(model.parameters(), lr=phase2_config['learning_rate'])
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=5, verbose=True)
    model = train_model(model, optimizer, scheduler, train_loader, val_loader, phase2_config)

    # --- FASE 3 ---
    logging.info("Cargando mejor modelo de Fase 2 para iniciar Fase 3...")
    checkpoint = torch.load(os.path.join(CONFIG['model_save_dir'], "best_model.pth"))
    model.load_state_dict(checkpoint['model_state_dict'])
    phase3_config = {'epochs': 30, 'learning_rate': 1e-5, 'ssim_loss_weight': 0.6, 'high_dbz_threshold_norm': 0.5, 'high_penalty_weight': 20, 'use_ssim_loss': True}
    optimizer = torch.optim.Adam(model.parameters(), lr=phase3_config['learning_rate'])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=phase3_config['epochs'])
    model = train_model(model, optimizer, scheduler, train_loader, val_loader, phase3_config)

    generate_prediction_netcdf(CONFIG)
    logging.info("Pipeline de entrenamiento en 3 fases completado.")

if __name__ == '__main__':
    main()

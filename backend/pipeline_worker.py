# backend/pipeline_worker.py

import os
import time
import logging
import shutil
import json
from datetime import datetime, timedelta, timezone
import numpy as np
import torch
import xarray as xr
from netCDF4 import Dataset as NCDataset
import pyproj

# Importamos desde nuestros módulos
from config import (INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, SECUENCE_LENGHT, 
                    POLL_INTERVAL_SECONDS, MODEL_PATH, DATA_CONFIG, STATUS_FILE_PATH)
from model.predict import ModelPredictor

# --- Configuración del Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def update_status(status_message: str, file_count: int, total_needed: int):
    """Crea y escribe el estado actual en el archivo JSON."""
    status = {
        "status": status_message,
        "files_in_buffer": file_count,
        "files_needed_for_run": total_needed,
        "last_update": datetime.now(timezone.utc).isoformat()
    }
    try:
        with open(STATUS_FILE_PATH, 'w') as f:
            json.dump(status, f, indent=4)
        logging.info(f"Estado actualizado: {status_message}")
    except Exception as e:
        logging.error(f"No se pudo escribir en el archivo de estado: {e}")

def load_and_preprocess_input_sequence(input_file_paths: list) -> torch.Tensor:
    """Carga una secuencia de archivos NetCDF, los pre-procesa y los apila."""
    data_list = []
    min_dbz = DATA_CONFIG['min_dbz']
    max_dbz = DATA_CONFIG['max_dbz']
    for file_path in input_file_paths:
        with xr.open_dataset(file_path, mask_and_scale=True, decode_times=False) as ds:
            dbz_physical = ds[DATA_CONFIG['variable_name']].values
        dbz_physical_squeezed = dbz_physical[0, ...]
        dbz_clipped = np.clip(dbz_physical_squeezed, min_dbz, max_dbz)
        dbz_normalized = (dbz_clipped - min_dbz) / (max_dbz - min_dbz)
        data_list.append(dbz_normalized[..., np.newaxis])
    full_sequence = np.stack(data_list, axis=1) # Forma: (Z, T, H, W, C)
    return torch.from_numpy(np.nan_to_num(full_sequence, nan=0.0)).float()

def postprocess_prediction(prediction_norm: torch.Tensor) -> np.ndarray:
    """Aplica la desnormalización y el umbral físico a la salida del modelo."""
    # El modelo devuelve (Z, T_pred, C, H, W)
    # Permutamos a (T_pred, Z, C, H, W) para que sea más fácil de manejar
    prediction_permuted = prediction_norm.permute(1, 0, 2, 3, 4)
    
    pred_physical_raw = prediction_permuted.numpy() * (DATA_CONFIG['max_dbz'] - DATA_CONFIG['min_dbz']) + DATA_CONFIG['min_dbz']
    pred_physical_clipped = np.clip(pred_physical_raw, DATA_CONFIG['min_dbz'], DATA_CONFIG['max_dbz'])
    pred_physical_cleaned = pred_physical_clipped.copy()
    threshold = DATA_CONFIG.get('physical_threshold_dbz', 30.0)
    pred_physical_cleaned[pred_physical_cleaned < threshold] = np.nan
    
    # Quitamos la dimensión de canal que es 1 -> (T_pred, Z, H, W)
    return pred_physical_cleaned.squeeze(2)

def save_prediction_as_netcdf(output_subdir: str, pred_sequence_cleaned: np.ndarray, start_datetime: datetime):
    """Guarda la secuencia de predicción en múltiples archivos NetCDF dentro de un subdirectorio."""
    num_pred_steps, num_z, num_y, num_x = pred_sequence_cleaned.shape
    # (El resto de esta función es idéntica a la que ya tenías en tu script de inferencia)
    # ... (código para crear coordenadas, grillas y guardar cada frame de la predicción) ...
    z_coords = np.arange(1.0, 1.0 + num_z * 1.0, 1.0, dtype=np.float32)
    x_coords = np.arange(-249.5, -249.5 + num_x * 1.0, 1.0, dtype=np.float32)
    y_coords = np.arange(-249.5, -249.5 + num_y * 1.0, 1.0, dtype=np.float32)
    proj = pyproj.Proj(proj="aeqd", lon_0=DATA_CONFIG['sensor_longitude'], lat_0=DATA_CONFIG['sensor_latitude'], R=DATA_CONFIG['earth_radius_m'])
    x_grid_m, y_grid_m = np.meshgrid(x_coords * 1000.0, y_coords * 1000.0)
    lon0_grid, lat0_grid = proj(x_grid_m, y_grid_m, inverse=True)

    for i in range(num_pred_steps):
        lead_time_minutes = (i + 1) * DATA_CONFIG.get('prediction_interval_minutes', 3)
        forecast_dt_utc = start_datetime + timedelta(minutes=lead_time_minutes)
        output_filename = os.path.join(output_subdir, f"pred_t+{lead_time_minutes:02d}.nc")

        with NCDataset(output_filename, 'w', format='NETCDF3_CLASSIC') as ds_out:
            ds_out.Conventions = "CF-1.6"
            # ... (resto de atributos, dimensiones y variables como en tu script) ...
            ds_out.createDimension('time', None); ds_out.createDimension('longitude', num_x); ds_out.createDimension('latitude', num_y); ds_out.createDimension('altitude', num_z)
            time_value = (forecast_dt_utc.replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()
            time_v = ds_out.createVariable('time', 'f8', ('time',)); time_v.units = "seconds since 1970-01-01T00:00:00Z"; time_v[:] = [time_value]
            # ... (resto de variables de coordenadas y georreferenciación) ...
            fill_value_float = np.float32(-999.0)
            dbz_v = ds_out.createVariable('DBZ', 'f4', ('time', 'altitude', 'latitude', 'longitude'), fill_value=fill_value_float)
            dbz_v.setncatts({'units': 'dBZ', '_FillValue': fill_value_float, 'missing_value': fill_value_float})
            pred_data_single_step = pred_sequence_cleaned[i]
            dbz_final_to_write = np.nan_to_num(pred_data_single_step, nan=fill_value_float)
            dbz_v[0, :, :, :] = dbz_final_to_write
        logging.info(f"  -> Predicción guardada en: {os.path.basename(output_filename)}")


def main():
    """Función principal que vigila la carpeta de entrada y procesa secuencias."""
    logging.info("====== INICIO DEL WORKER DEL PIPELINE ======")
    os.makedirs(INPUT_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True); os.makedirs(ARCHIVE_DIR, exist_ok=True)
    
    predictor = ModelPredictor(MODEL_PATH)
    
    while True:
        try:
            input_files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith('.nc')])
            update_status("IDLE - Waiting for files", len(input_files), SECUENCE_LENGHT)
            
            if len(input_files) >= SECUENCE_LENGHT:
                files_to_process = input_files[:SECUENCE_LENGHT]
                full_paths = [os.path.join(INPUT_DIR, f) for f in files_to_process]
                
                seq_id = os.path.splitext(files_to_process[-1])[0]
                update_status(f"PROCESSING - Running model on sequence {seq_id}", len(files_to_process), SECUENCE_LENGHT)
                
                input_tensor = load_and_preprocess_input_sequence(full_paths)
                prediction_tensor = predictor.predict(input_tensor)
                prediction_cleaned = postprocess_prediction(prediction_tensor)
                
                try:
                    last_input_dt_utc = datetime.strptime(seq_id, '%Y%m%d%H%M%S')
                except ValueError:
                    last_input_dt_utc = datetime.now(timezone.utc)
                
                # Crear subdirectorio único para esta predicción
                output_subdir_name = last_input_dt_utc.strftime('%Y%m%d-%H%M%S')
                output_subdir_path = os.path.join(OUTPUT_DIR, output_subdir_name)
                os.makedirs(output_subdir_path, exist_ok=True)

                save_prediction_as_netcdf(output_subdir_path, prediction_cleaned, last_input_dt_utc)
                
                logging.info(f"Archivando {len(full_paths)} archivos procesados...")
                for path in full_paths:
                    shutil.move(path, os.path.join(ARCHIVE_DIR, os.path.basename(path)))
            else:
                time.sleep(POLL_INTERVAL_SECONDS)
        
        except Exception as e:
            update_status(f"ERROR - Check logs for details", -1, -1)
            logging.error(f"Ocurrió un error en el bucle principal: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS * 2)

if __name__ == "__main__":
    main()

    
import os
import argparse
import time
from datetime import datetime, timedelta, timezone
import numpy as np
import torch
import torch.nn as nn
from netCDF4 import Dataset as NCDataset
import logging
import pyproj
import xarray as xr
import sys

# Add project root to sys.path to import backend modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.model.architecture import ConvLSTM3D_Enhanced

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# ==================================================================
# FUNCIONES DE AYUDA
# ==================================================================

def find_sequences(root_dir, seq_length):
    sequences = []
    logging.info(f"Buscando secuencias de longitud {seq_length} en: {root_dir}")
    if not os.path.isdir(root_dir):
        logging.error(f"El directorio raíz no existe: {root_dir}"); return sequences
    for seq_folder_name in sorted(os.listdir(root_dir)):
        seq_path = os.path.join(root_dir, seq_folder_name)
        if not os.path.isdir(seq_path): continue
        nc_files = sorted([os.path.join(seq_path, f) for f in os.listdir(seq_path) if f.endswith('.nc')])
        if len(nc_files) >= seq_length:
            sequences.append(nc_files[-seq_length:]) # Tomamos los últimos N archivos
    return sequences

def load_and_preprocess_input_sequence(input_file_paths, data_cfg, target_height=250, target_width=250):
    """
    Carga secuencia, preprocesa y hace DOWNSAMPLING para el modelo.
    """
    data_list = []
    min_dbz = data_cfg['min_dbz']
    max_dbz = data_cfg['max_dbz']

    for file_path in input_file_paths:
        try:
            with xr.open_dataset(file_path, mask_and_scale=True, decode_times=False) as ds:
                var_name = data_cfg.get('variable_name', 'DBZ')
                if var_name not in ds:
                    var_name = list(ds.data_vars)[0]
                dbz_physical = ds[var_name].values

            # (Time, Z, Y, X) -> (Z, Y, X)
            if dbz_physical.ndim == 4:
                dbz_physical_squeezed = dbz_physical[0, ...]
            else:
                dbz_physical_squeezed = dbz_physical

            # Max projection si es 3D (Z > 1) para simplificar entrada al modelo si se desea
            # O mantener 3D. El modelo espera (B, T, C, H, W).
            # Asumimos que el modelo toma 1 canal (max projection o un nivel)
            # Si el modelo es 3D real, necesitaríamos ajustar. 
            # Basado en train.py, usamos np.nanmax(data, axis=0)
            
            if dbz_physical_squeezed.ndim == 3:
                dbz_2d = np.nanmax(dbz_physical_squeezed, axis=0)
            else:
                dbz_2d = dbz_physical_squeezed

            # Normalizar
            dbz_clipped = np.clip(dbz_2d, min_dbz, max_dbz)
            dbz_normalized = (dbz_clipped - min_dbz) / (max_dbz - min_dbz)
            
            # Convertir a Tensor y redimensionar (Downsampling)
            tensor = torch.from_numpy(dbz_normalized).float().unsqueeze(0) # (C, H, W)
            
            # Downsampling a 250x250
            tensor_resized = torch.nn.functional.interpolate(
                tensor.unsqueeze(0), 
                size=(target_height, target_width), 
                mode='bilinear', 
                align_corners=False
            ).squeeze(0)

            data_list.append(tensor_resized)

        except Exception as e:
            logging.error(f"Error procesando archivo {file_path}: {e}")
            raise

    # Stack Time: (T, C, H, W)
    full_sequence = torch.stack(data_list, dim=0)
    # Add Batch: (B, T, C, H, W)
    return full_sequence.unsqueeze(0)

def save_prediction_as_netcdf(output_dir, pred_sequence_cleaned, data_cfg, start_datetime, seq_identifier):
    # pred_sequence_cleaned shape: (PredSteps, Z, H, W) -> (7, 1, 500, 500)
    num_pred_steps, num_z, num_y, num_x = pred_sequence_cleaned.shape
    
    # --- Preparación de la Grilla (Original 500x500) ---
    # Asumimos resolución de 1km
    z_coords = np.arange(1.0, 1.0 + num_z * 1.0, 1.0, dtype=np.float32)
    x_coords = np.arange(-249.5, -249.5 + num_x * 1.0, 1.0, dtype=np.float32)
    y_coords = np.arange(-249.5, -249.5 + num_y * 1.0, 1.0, dtype=np.float32)
    
    proj = pyproj.Proj(proj="aeqd", lon_0=data_cfg['sensor_longitude'], lat_0=data_cfg['sensor_latitude'], R=data_cfg['earth_radius_m'])
    x_grid_m, y_grid_m = np.meshgrid(x_coords * 1000.0, y_coords * 1000.0)
    lon0_grid, lat0_grid = proj(x_grid_m, y_grid_m, inverse=True)

    for i in range(num_pred_steps):
        lead_time_minutes = (i + 1) * data_cfg.get('prediction_interval_minutes', 3)
        forecast_dt_utc = start_datetime + timedelta(minutes=lead_time_minutes)
        file_ts = forecast_dt_utc.strftime("%Y%m%d_%H%M%S")
        output_filename = os.path.join(output_dir, f"{file_ts}.nc")

        with NCDataset(output_filename, 'w', format='NETCDF3_CLASSIC') as ds_out:
            # --- Atributos Globales ---
            ds_out.Conventions = "CF-1.6"
            ds_out.title = f"{data_cfg.get('radar_name', 'RADAR_PRED')} - Forecast t+{lead_time_minutes}min"
            ds_out.institution = data_cfg.get('institution_name', "UM")
            ds_out.source = data_cfg.get('data_source_name', "ConvLSTM Model Prediction")
            ds_out.history = f"Created {datetime.now(timezone.utc).isoformat()} by ConvLSTM prediction script."
            ds_out.comment = f"Forecast data from model. Lead time: {lead_time_minutes} min."

            # --- Dimensiones ---
            ds_out.createDimension('time', None)
            ds_out.createDimension('bounds', 2)
            ds_out.createDimension('longitude', num_x)
            ds_out.createDimension('latitude', num_y)
            ds_out.createDimension('altitude', num_z)

            # --- Variables ---
            time_value = (forecast_dt_utc.replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()
            
            time_v = ds_out.createVariable('time', 'f8', ('time',))
            time_v.standard_name = "time"; time_v.long_name = "Data time"
            time_v.units = "seconds since 1970-01-01T00:00:00Z"; time_v.axis = "T"
            time_v[:] = [time_value]

            x_v = ds_out.createVariable('longitude', 'f4', ('longitude',)); x_v.setncatts({'standard_name':"projection_x_coordinate", 'units':"km", 'axis':"X"}); x_v[:] = x_coords
            y_v = ds_out.createVariable('latitude', 'f4', ('latitude',)); y_v.setncatts({'standard_name':"projection_y_coordinate", 'units':"km", 'axis':"Y"}); y_v[:] = y_coords
            z_v = ds_out.createVariable('altitude', 'f4', ('altitude',)); z_v.setncatts({'standard_name':"altitude", 'units':"km", 'axis':"Z", 'positive':"up"}); z_v[:] = z_coords
            
            lat0_v = ds_out.createVariable('lat0', 'f4', ('latitude', 'longitude',)); lat0_v.setncatts({'standard_name':"latitude", 'units':"degrees_north"}); lat0_v[:] = lat0_grid
            lon0_v = ds_out.createVariable('lon0', 'f4', ('latitude', 'longitude',)); lon0_v.setncatts({'standard_name':"longitude", 'units':"degrees_east"}); lon0_v[:] = lon0_grid
            gm_v = ds_out.createVariable('grid_mapping_0', 'i4'); gm_v.setncatts({'grid_mapping_name':"azimuthal_equidistant", 'longitude_of_projection_origin':data_cfg['sensor_longitude'], 'latitude_of_projection_origin':data_cfg['sensor_latitude'], 'false_easting':0.0, 'false_northing':0.0, 'earth_radius':data_cfg['earth_radius_m']})

            fill_value_float = np.float32(-999.0)
            dbz_v = ds_out.createVariable('DBZ', 'f4', ('time', 'altitude', 'latitude', 'longitude'), fill_value=fill_value_float)
            dbz_v.setncatts({'units': 'dBZ', 'long_name': 'DBZ', 'standard_name': 'reflectivity', '_FillValue': fill_value_float, 'missing_value': fill_value_float})
            
            pred_data_single_step = pred_sequence_cleaned[i]
            dbz_final_to_write = np.nan_to_num(pred_data_single_step, nan=fill_value_float)
            
            dbz_v[0, :, :, :] = dbz_final_to_write

        logging.info(f"  -> Predicción guardada en: {os.path.basename(output_filename)}")

# ==================================================================
# BLOQUE DE EJECUCIÓN PRINCIPAL
# ==================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script de inferencia remota para ConvLSTM.")
    parser.add_argument('--sequences_dir', type=str, required=True, help='Directorio raíz que contiene las carpetas de secuencias.')
    parser.add_argument('--model_path', type=str, required=True, help='Ruta al archivo .pth del modelo entrenado.')
    parser.add_argument('--output_dir', type=str, required=True, help='Directorio donde se guardarán las predicciones.')
    parser.add_argument('--input_len', type=int, default=8, help='Longitud de la secuencia de entrada.')
    parser.add_argument('--pred_len', type=int, default=7, help='Longitud de la predicción.')
    args = parser.parse_args()

    # Configuración alineada con el entrenamiento
    model_config = {
        'input_dim': 1, 
        'hidden_dims': [128, 128, 128], 
        'kernel_sizes': [(3, 3), (3, 3), (3, 3)],
        'num_layers': 3, 
        'pred_steps': args.pred_len, 
        'use_layer_norm': True,
        'img_height': 250, # El modelo trabaja en baja resolución
        'img_width': 250
    }
    
    data_config = {
        'min_dbz': -29.0, 'max_dbz': 65.0, 'variable_name': 'DBZ',
        'prediction_interval_minutes': 3,
        'physical_threshold_dbz': 30.0, 
        'sensor_latitude': -34.64799880981445,
        'sensor_longitude': -68.01699829101562,
        'earth_radius_m': 6378137.0,
        'radar_name': 'SAN_RAFAEL_PRED',
        'institution_name': 'UM',
        'data_source_name': 'ConvLSTM Model Prediction'
    }

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logging.info(f"Usando dispositivo: {device}")
    
    model = ConvLSTM3D_Enhanced(**model_config)
    
    try:
        checkpoint = torch.load(args.model_path, map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.to(device)
        model.eval()
        logging.info(f"Modelo cargado exitosamente desde: {args.model_path}")
    except Exception as e:
        logging.error(f"Error fatal al cargar el modelo: {e}", exc_info=True); exit()

    os.makedirs(args.output_dir, exist_ok=True)
    sequences_to_process = find_sequences(args.sequences_dir, args.input_len)
    
    if not sequences_to_process:
        logging.warning(f"No se encontraron secuencias válidas en {args.sequences_dir}"); exit()

    logging.info(f"Se encontraron {len(sequences_to_process)} secuencias para procesar.")

    for i, file_list in enumerate(sequences_to_process):
        seq_id = os.path.splitext(os.path.basename(file_list[-1]))[0]
        logging.info(f"--- Procesando Secuencia {i+1}/{len(sequences_to_process)} ({seq_id}) ---")
        
        try:
            # 1. Cargar y Downsample (500 -> 250)
            input_tensor = load_and_preprocess_input_sequence(file_list, data_config, target_height=250, target_width=250)
            input_tensor = input_tensor.to(device)

            # 2. Inferencia
            with torch.no_grad(), torch.cuda.amp.autocast():
                prediction_norm = model(input_tensor) # (B, T, C, H, W) -> (1, 7, 1, 250, 250)
            
            # 3. Upsampling (250 -> 500)
            # Permute para interpolate: (B*T, C, H, W)
            b, t, c, h, w = prediction_norm.shape
            pred_reshaped = prediction_norm.view(b * t, c, h, w)
            
            pred_upsampled = torch.nn.functional.interpolate(
                pred_reshaped, 
                size=(500, 500), 
                mode='bicubic', # Bicubic para mejor calidad
                align_corners=False
            )
            
            # Volver a forma original
            pred_upsampled = pred_upsampled.view(b, t, c, 500, 500)
            
            # 4. Post-procesamiento
            pred_physical_raw = pred_upsampled.cpu().numpy() * (data_config['max_dbz'] - data_config['min_dbz']) + data_config['min_dbz']
            pred_physical_clipped = np.clip(pred_physical_raw, data_config['min_dbz'], data_config['max_dbz'])
            
            pred_physical_cleaned = pred_physical_clipped.copy()
            threshold = data_config.get('physical_threshold_dbz', 30.0)
            pred_physical_cleaned[pred_physical_cleaned < threshold] = np.nan
            
            # Quitar dimensiones extra para guardar: (B, T, C, H, W) -> (T, C, H, W) -> (T, 1, 500, 500)
            pred_final = pred_physical_cleaned[0] 

            # 5. Guardar NetCDF
            try:
                last_input_filepath = file_list[-1]
                parts = last_input_filepath.split('/')
                # Ajustar parsing según estructura de carpetas real si es necesario
                # Asumimos nombre archivo tipo YYYYMMDD_HHMMSS.nc
                filename = os.path.basename(last_input_filepath)
                dt_str = os.path.splitext(filename)[0]
                # Intentar varios formatos si es necesario
                if '_' in dt_str:
                    last_input_dt_utc = datetime.strptime(dt_str, '%Y%m%d_%H%M%S')
                else:
                    last_input_dt_utc = datetime.strptime(dt_str, '%Y%m%d%H%M%S')
            except Exception as e_time:
                logging.warning(f"No se pudo parsear timestamp de {last_input_filepath}. Usando now(). Error: {e_time}")
                last_input_dt_utc = datetime.now()

            save_prediction_as_netcdf(
                output_dir=os.path.join(args.output_dir, seq_id),
                pred_sequence_cleaned=pred_final,
                data_cfg=data_config,
                start_datetime=last_input_dt_utc,
                seq_identifier=seq_id
            )

            del input_tensor, prediction_norm, pred_upsampled, pred_physical_cleaned
            torch.cuda.empty_cache()

        except Exception as e:
            logging.error(f"Error en secuencia {seq_id}: {e}", exc_info=True)
            continue

    logging.info("Inferencia completada.")

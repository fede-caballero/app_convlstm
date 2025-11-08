import os
import time
import logging
import shutil
import json
import subprocess
from datetime import datetime, timedelta, timezone
import numpy as np
import torch
import torch.nn.functional as F
import xarray as xr
from netCDF4 import Dataset as NCDataset
import pyproj
import glob
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

# Importamos desde nuestros módulos
from config import (
    MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, 
    POLL_INTERVAL_SECONDS, MODEL_PATH, DATA_CONFIG, STATUS_FILE_PATH, 
    MDV_OUTPUT_DIR, IMAGE_OUTPUT_DIR, LROSE_PARAMS_DIR
)
from model.architecture import PredRNNpp_3D

# --- Configuración del Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# --- Adaptamos la configuración a los nuevos parámetros del modelo ---
SECUENCE_LENGHT = 10
PRED_LENGHT = 5
ORIGINAL_SIZE = (500, 500)
DOWNSAMPLE_SIZE = (250, 250)
Z_LEVELS = 18

def generar_imagen_transparente_y_bounds(nc_file_path: str, output_image_path: str, skip_levels: int = 2):
    try:
        logging.info(f"Generando imagen transparente para: {os.path.basename(nc_file_path)}")
        ds = xr.open_dataset(nc_file_path, mask_and_scale=True, decode_times=False)
        
        lon_name = 'longitude'
        lat_name = 'latitude'
        
        x = ds[lon_name].values
        y = ds[lat_name].values
        dbz_data = ds['DBZ'].squeeze().values

        if dbz_data.ndim == 3 and dbz_data.shape[0] > skip_levels:
            composite_data_2d = np.nanmax(dbz_data[skip_levels:, :, :], axis=0)
        else:
            composite_data_2d = np.nanmax(dbz_data, axis=0)

        proj_info = ds['grid_mapping_0'].attrs
        lon_0 = proj_info['longitude_of_projection_origin']
        lat_0 = proj_info['latitude_of_projection_origin']
        projection = ccrs.AzimuthalEquidistant(central_longitude=lon_0, central_latitude=lat_0)

        fig = plt.figure(figsize=(10, 10), dpi=150)
        ax = fig.add_subplot(1, 1, 1)
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        ax.set_axis_off()
        
        # Usar imshow para la imagen principal
        cmap = plt.get_cmap('jet')
        ax.imshow(np.ma.masked_invalid(composite_data_2d), cmap=cmap, origin='lower', vmin=0, vmax=70)
        
        plt.tight_layout(pad=0)
        plt.savefig(output_image_path, dpi=150, transparent=True, bbox_inches='tight', pad_inches=0)
        plt.close(fig)

        x_min, x_max = x.min() * 1000, x.max() * 1000
        y_min, y_max = y.min() * 1000, y.max() * 1000
        geo_proj = ccrs.Geodetic()
        sw_corner = geo_proj.transform_point(x_min, y_min, projection)
        ne_corner = geo_proj.transform_point(x_max, y_max, projection)
        bounds = [[float(sw_corner[1]), float(sw_corner[0])], [float(ne_corner[1]), float(ne_corner[0])]]
        
        logging.info(f"  -> Imagen transparente guardada en: {output_image_path}")
        return bounds
    except Exception as e:
        logging.error(f"No se pudo generar la imagen para {nc_file_path}: {e}", exc_info=True)
        return None

def update_status(status_message: str, file_count: int, total_needed: int):
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
    data_list = []
    min_dbz = DATA_CONFIG['min_dbz']
    max_dbz = DATA_CONFIG['max_dbz']
    for file_path in input_file_paths:
        with xr.open_dataset(file_path, mask_and_scale=True, decode_times=False) as ds:
            dbz_physical = ds[DATA_CONFIG['variable_name']].values[0]
        dbz_clipped = np.clip(dbz_physical, min_dbz, max_dbz)
        dbz_normalized = (dbz_clipped - min_dbz) / (max_dbz - min_dbz)
        dbz_tensor = torch.from_numpy(dbz_normalized).float()
        dbz_tensor_unsqueezed = dbz_tensor.unsqueeze(1)
        downsampled_tensor = F.avg_pool2d(dbz_tensor_unsqueezed, kernel_size=2)
        data_list.append(downsampled_tensor.squeeze(1).numpy())
    full_sequence = np.stack(data_list, axis=0)
    full_sequence = full_sequence[np.newaxis, :, np.newaxis, ...] # (B=1, T, C=1, Z, H, W)
    return torch.from_numpy(np.nan_to_num(full_sequence, nan=0.0)).float()

def postprocess_prediction(prediction_norm: torch.Tensor) -> np.ndarray:
    b, t, c, z, h, w = prediction_norm.shape
    pred_low_res_reshaped = prediction_norm.reshape(b * t, c * z, h, w)
    pred_high_res = F.interpolate(pred_low_res_reshaped, size=ORIGINAL_SIZE, mode='bilinear', align_corners=False)
    pred_high_res = pred_high_res.reshape(b, t, c, z, ORIGINAL_SIZE[0], ORIGINAL_SIZE[1])
    min_dbz, max_dbz = DATA_CONFIG['min_dbz'], DATA_CONFIG['max_dbz']
    pred_physical = pred_high_res.cpu().numpy() * (max_dbz - min_dbz) + min_dbz
    pred_physical_clipped = np.clip(pred_physical, min_dbz, max_dbz)
    pred_physical_cleaned = pred_physical_clipped.copy()
    threshold = DATA_CONFIG.get('physical_threshold_dbz', 0) # Umbral bajo para no eliminar datos válidos
    pred_physical_cleaned[pred_physical_cleaned < threshold] = np.nan
    return pred_physical_cleaned[0, :, 0, :, :, :]

def save_prediction_as_netcdf(output_subdir: str, pred_sequence_cleaned: np.ndarray, data_cfg: dict, start_datetime: datetime):
    num_pred_steps, num_z, num_y, num_x = pred_sequence_cleaned.shape
    z_coords = np.arange(1.0, 1.0 + num_z * 1.0, 1.0, dtype=np.float32)
    x_coords = np.arange(-249.5, -249.5 + num_x * 1.0, 1.0, dtype=np.float32)
    y_coords = np.arange(-249.5, -249.5 + num_y * 1.0, 1.0, dtype=np.float32)
    
    proj = pyproj.Proj(proj="aeqd", lon_0=data_cfg['sensor_longitude'], lat_0=data_cfg['sensor_latitude'], R=data_cfg['earth_radius_m'])
    x_grid_m, y_grid_m = np.meshgrid(x_coords * 1000.0, y_coords * 1000.0)
    lon0_grid, lat0_grid = proj(x_grid_m, y_grid_m, inverse=True)

    saved_files = []
    for i in range(num_pred_steps):
        lead_time_minutes = (i + 1) * data_cfg.get('prediction_interval_minutes', 3)
        forecast_dt_utc = start_datetime + timedelta(minutes=lead_time_minutes)
        output_filename = os.path.join(output_subdir, f"pred_t+{lead_time_minutes:02d}_{forecast_dt_utc.strftime('%Y%m%d%H%M')}.nc")
        
        with NCDataset(output_filename, 'w', format='NETCDF3_CLASSIC') as ds_out:
            # Atributos globales
            ds_out.setncattr('Conventions', "CF-1.6")
            ds_out.setncattr('title', f"SAN_RAFAEL_PRED - Forecast t+{lead_time_minutes}min")
            ds_out.setncattr('institution', "UM")
            ds_out.setncattr('source', "PredRNN++ Model Prediction")
            ds_out.setncattr('history', f"Created {datetime.now(timezone.utc).isoformat()} by PredRNN++ prediction script.")
            ds_out.setncattr('comment', f"Forecast data from model. Lead time: {lead_time_minutes} min.")

            # Dimensiones
            ds_out.createDimension('time', 1)
            ds_out.createDimension('longitude', num_x)
            ds_out.createDimension('latitude', num_y)
            ds_out.createDimension('altitude', num_z)

            # Variables de coordenadas
            times = ds_out.createVariable('time', 'f8', ('time',))
            times.units = "seconds since 1970-01-01 00:00:00 Z"
            times[:] = (forecast_dt_utc - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()

            longitudes = ds_out.createVariable('longitude', 'f4', ('longitude',))
            longitudes.units = 'km'
            longitudes[:] = x_coords

            latitudes = ds_out.createVariable('latitude', 'f4', ('latitude',))
            latitudes.units = 'km'
            latitudes[:] = y_coords

            altitudes = ds_out.createVariable('altitude', 'f4', ('altitude',))
            altitudes.units = 'km'
            altitudes[:] = z_coords
            
            # Variables de mapeo y geo-referencia
            grid_mapping = ds_out.createVariable('grid_mapping_0', 'i4')
            grid_mapping.grid_mapping_name = "azimuthal_equidistant"
            grid_mapping.longitude_of_projection_origin = data_cfg['sensor_longitude']
            grid_mapping.latitude_of_projection_origin = data_cfg['sensor_latitude']
            grid_mapping.false_easting = 0.0
            grid_mapping.false_northing = 0.0
            grid_mapping.earth_radius = data_cfg['earth_radius_m']

            lon0 = ds_out.createVariable('lon0', 'f4', ('latitude', 'longitude'))
            lon0.units = "degrees_east"
            lon0[:] = lon0_grid

            lat0 = ds_out.createVariable('lat0', 'f4', ('latitude', 'longitude'))
            lat0.units = "degrees_north"
            lat0[:] = lat0_grid

            # Variable de datos (DBZ)
            dbz_v = ds_out.createVariable('DBZ', 'f4', ('time', 'altitude', 'latitude', 'longitude'), fill_value=-999.0)
            dbz_v.setncatts({'long_name': 'DBZ', 'standard_name': 'reflectivity', 'units': 'dBZ', 'missing_value': -999.0, 'grid_mapping': 'grid_mapping_0'})
            dbz_v[0, :, :, :] = np.nan_to_num(pred_sequence_cleaned[i], nan=-999.0)
        
        logging.info(f"  -> Predicción guardada en: {os.path.basename(output_filename)}")
        saved_files.append(output_filename)
    return saved_files

def convert_mdv_to_nc(mdv_filepath: str, final_output_dir: str, params_path: str):
    try:
        base_name = os.path.splitext(os.path.basename(mdv_filepath))[0]
        output_nc_path = os.path.join(final_output_dir, f"{base_name}.nc")
        
        command = [
            "Mdv2NetCDF", 
            "-f", mdv_filepath, 
            "-p", params_path,
            "-o", output_nc_path
        ]
        
        logging.info(f"Convirtiendo {base_name}.mdv a NetCDF...")
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_nc_path):
            logging.info(f"  -> Conversión exitosa: {output_nc_path}")
            return True
        else:
            logging.error(f"Fallo la conversión de {mdv_filepath}.")
            logging.error(f"STDOUT: {result.stdout}")
            logging.error(f"STDERR: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Excepción durante la conversión de MDV a NC: {e}", exc_info=True)
        return False

def convert_predictions_to_mdv(nc_input_dir: str, mdv_output_dir: str, params_template_path: str):
    nc_files = sorted(glob.glob(os.path.join(nc_input_dir, "*.nc")))
    if not nc_files:
        logging.warning(f"No se encontraron archivos NetCDF en {nc_input_dir} para convertir a MDV.")
        return

    logging.info(f"Iniciando conversión de {len(nc_files)} archivos NetCDF a MDV...")
    for nc_file in nc_files:
        try:
            base_name = os.path.splitext(os.path.basename(nc_file))[0]
            output_mdv_path = os.path.join(mdv_output_dir, f"{base_name}.mdv")
            
            command = [
                "NcGeneric2Mdv",
                "-f", nc_file,
                "-p", params_template_path,
                "-o", output_mdv_path
            ]
            
            logging.info(f"Convirtiendo {os.path.basename(nc_file)} a MDV...")
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(output_mdv_path):
                logging.info(f"  -> Conversión a MDV exitosa: {output_mdv_path}")
            else:
                logging.error(f"Fallo la conversión a MDV para {nc_file}.")
                logging.error(f"STDOUT: {result.stdout}")
                logging.error(f"STDERR: {result.stderr}")
        except Exception as e:
            logging.error(f"Excepción durante la conversión a MDV para {nc_file}: {e}", exc_info=True)

def main():
    logging.info("====== INICIO DEL WORKER DEL PIPELINE (vPredRNN) ======")
    # Asegurarse de que todos los directorios necesarios existan
    for path in [MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, MDV_OUTPUT_DIR, IMAGE_OUTPUT_DIR, LROSE_PARAMS_DIR]:
        os.makedirs(path, exist_ok=True)
    
    # --- Carga del modelo PredRNN++ ---
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logging.info(f"Usando dispositivo: {device}")
    
    model_config = {
        'model_input_dim': 1, 'model_hidden_dims': [64, 64, 64],
        'model_kernel_sizes': [(3,3,3), (3,3,3), (3,3,3)], 'model_num_layers': 3,
        'model_use_layer_norm': True, 'seq_len': SECUENCE_LENGHT, 'pred_len': PRED_LENGHT
    }
    model = PredRNNpp_3D(model_config).to(device)
    
    if os.path.exists(MODEL_PATH):
        checkpoint = torch.load(MODEL_PATH, map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        logging.info(f"Modelo PredRNN++ cargado desde {MODEL_PATH}")
    else:
        logging.error(f"No se encontró el archivo del modelo en {MODEL_PATH}. El worker no puede iniciar.")
        return

    # Rutas a los archivos de parámetros de LROSE
    mdv_to_nc_params = os.path.join(LROSE_PARAMS_DIR, 'Mdv2NetCDF.params')
    nc_to_mdv_params = os.path.join(LROSE_PARAMS_DIR, 'params.nc2mdv.final')

    while True:
        try:
            # --- 1. Procesar nuevos archivos MDV ---
            mdv_files = sorted([f for f in os.listdir(MDV_INBOX_DIR) if f.endswith('.mdv')])
            if mdv_files:
                logging.info(f"Se encontraron {len(mdv_files)} nuevos archivos MDV para procesar.")
                for mdv_file in mdv_files:
                    mdv_path = os.path.join(MDV_INBOX_DIR, mdv_file)
                    if convert_mdv_to_nc(mdv_path, INPUT_DIR, mdv_to_nc_params):
                        # Mover a archivo si la conversión fue exitosa
                        shutil.move(mdv_path, os.path.join(MDV_ARCHIVE_DIR, mdv_file))
                        logging.info(f"Archivo MDV movido a: {MDV_ARCHIVE_DIR}")
            
            # --- 2. Verificar si hay suficientes archivos para una secuencia ---
            input_files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith('.nc')])
            if len(input_files) < SECUENCE_LENGHT:
                update_status("IDLE - Esperando archivos NC", len(input_files), SECUENCE_LENGHT)
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            # --- 3. Preparar y ejecutar la predicción ---
            files_to_process = input_files[-SECUENCE_LENGHT:]
            full_paths = [os.path.join(INPUT_DIR, f) for f in files_to_process]
            seq_id = os.path.splitext(files_to_process[-1])[0]
            update_status(f"Procesando secuencia {seq_id}", len(files_to_process), SECUENCE_LENGHT)
            
            logging.info(f"Iniciando predicción para la secuencia que termina en {files_to_process[-1]}")
            input_tensor = load_and_preprocess_input_sequence(full_paths).to(device)
            mask_false = torch.zeros((1, PRED_LENGHT, 1, Z_LEVELS, DOWNSAMPLE_SIZE[0], DOWNSAMPLE_SIZE[1]), dtype=torch.bool).to(device)
            
            with torch.no_grad():
                prediction_tensor = model(input_tensor, mask_false)
            
            prediction_cleaned = postprocess_prediction(prediction_tensor)
            
            try:
                # Extraer datetime del último archivo de la secuencia
                last_input_dt_utc = datetime.strptime(seq_id, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            except ValueError:
                logging.warning("No se pudo parsear la fecha del nombre de archivo, usando la hora actual.")
                last_input_dt_utc = datetime.now(timezone.utc)
            
            # --- 4. Guardar resultados ---
            output_subdir_name = last_input_dt_utc.strftime('%Y%m%d-%H%M%S')
            output_subdir_path = os.path.join(OUTPUT_DIR, output_subdir_name)
            os.makedirs(output_subdir_path, exist_ok=True)
            
            # Guardar predicciones en NetCDF
            saved_nc_files = save_prediction_as_netcdf(output_subdir_path, prediction_cleaned, DATA_CONFIG, last_input_dt_utc)

            # Convertir predicciones a MDV
            mdv_pred_output_dir = os.path.join(MDV_OUTPUT_DIR, output_subdir_name)
            os.makedirs(mdv_pred_output_dir, exist_ok=True)
            convert_predictions_to_mdv(output_subdir_path, mdv_pred_output_dir, nc_to_mdv_params)

            # Generar imágenes para la web
            image_pred_output_dir = os.path.join(IMAGE_OUTPUT_DIR, output_subdir_name)
            os.makedirs(image_pred_output_dir, exist_ok=True)
            for nc_file in saved_nc_files:
                base_name = os.path.splitext(os.path.basename(nc_file))[0]
                img_path = os.path.join(image_pred_output_dir, f"{base_name}.png")
                generar_imagen_transparente_y_bounds(nc_file, img_path)

            # --- 5. Limpiar y archivar ---
            logging.info("Archivando archivos de entrada procesados...")
            for file_path in full_paths:
                shutil.move(file_path, os.path.join(ARCHIVE_DIR, os.path.basename(file_path)))
            logging.info(f"{len(full_paths)} archivos movidos a {ARCHIVE_DIR}.")

        except Exception as e:
            update_status("ERROR", -1, -1)
            logging.error(f"Error en el bucle principal: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS * 2)

if __name__ == "__main__":
    main()
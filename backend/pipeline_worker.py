import os
import time
import logging
import shutil
import json
import subprocess
from datetime import datetime, timedelta, timezone
import numpy as np
import torch
import xarray as xr
from netCDF4 import Dataset as NCDataset
import pyproj
import glob

# Importamos desde nuestros módulos
from config import (MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, 
                    SECUENCE_LENGHT, POLL_INTERVAL_SECONDS, MODEL_PATH, 
                    DATA_CONFIG, STATUS_FILE_PATH, MDV_OUTPUT_DIR)
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


def convert_mdv_to_nc(mdv_filepath: str, final_output_dir: str, params_path: str):
    """
    Ejecuta Mdv2NetCDF en un directorio temporal, encuentra el archivo .nc,
    lo renombra al formato YYYYMMDDHHMMSS.nc (para un ordenamiento correcto)
    y lo mueve al directorio de salida final, limpiando los archivos temporales.
    """
    mdv_filename = os.path.basename(mdv_filepath)
    logging.info(f"Iniciando conversión de {mdv_filename}...")

    # --- 1. Crear un entorno de trabajo temporal y aislado ---
    temp_work_dir = "/app/temp_conversion_workspace"
    if os.path.exists(temp_work_dir):
        shutil.rmtree(temp_work_dir)
    os.makedirs(temp_work_dir)

    original_dir = os.getcwd()
    os.chdir(temp_work_dir)

    try:
        # --- 2. Ejecutar el comando validado ---
        command = [
            "Mdv2NetCDF",
            "-params", params_path,
            "-f", os.path.abspath(mdv_filepath)
        ]
        
        logging.info(f"Ejecutando comando: {' '.join(command)}")
        result = subprocess.run(command, check=True, capture_output=True, text=True)

        # --- 3. Encontrar, renombrar y mover el archivo de salida ---
        search_path = os.path.join(temp_work_dir, "netCDF", "*.nc")
        nc_files_found = glob.glob(search_path)

        if not nc_files_found:
            logging.error("Conversión reportó éxito, pero no se encontró ningún archivo .nc.")
            return False

        created_nc_path = nc_files_found[0]
        base_nc_name = os.path.basename(created_nc_path) # ej: ncfdata20080220_000437.nc
        
        # --- LÓGICA DE RENOMBRADO DEFINITIVA Y ROBUSTA ---
        try:
            # Quitamos 'ncfdata', '.nc' y unimos fecha y hora
            parts = base_nc_name.replace('ncfdata', '').replace('.nc', '').split('_')
            final_filename = f"{parts[0]}{parts[1]}.nc" # -> 20080220000437.nc
        except IndexError:
            logging.warning(f"No se pudo parsear el nombre '{base_nc_name}'. Usando nombre original.")
            final_filename = base_nc_name

        final_nc_path = os.path.join(final_output_dir, final_filename)
        
        logging.info(f"Moviendo y renombrando '{base_nc_name}' a '{final_nc_path}'")
        shutil.move(created_nc_path, final_nc_path)
        
        logging.info("Conversión y limpieza completadas exitosamente.")
        return True
    
    except subprocess.CalledProcessError as e:
        logging.error(f"Falló la conversión de {mdv_filename}.")
        logging.error(f"Comando: {' '.join(command)}")
        logging.error(f"Error de LROSE: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error("Error crítico: 'Mdv2NetCDF' no se encontró.")
        return False
    
    finally:
        # --- 4. Limpieza ---
        os.chdir(original_dir)
        if os.path.exists(temp_work_dir):
            shutil.rmtree(temp_work_dir)

def convert_predictions_to_mdv(nc_input_dir: str, mdv_output_dir: str, params_template_path: str):
    """
    Replica la lógica del script post_process.sh:
    1. Configura el entorno.
    2. Crea un archivo de parámetros temporal.
    3. Ejecuta NcGeneric2Mdv.
    4. Renombra los archivos de salida al formato HHMMSS.mdv.
    """
    logging.info(f"Iniciando conversión de NetCDF en '{nc_input_dir}' a MDV en '{mdv_output_dir}'")

    # --- Pasos 1, 2 y 3 se mantienen igual ---
    mdv_env = os.environ.copy()
    mdv_env["MDV_WRITE_FORMAT"] = "FORMAT_MDV"

    try:
        with open(params_template_path, 'r') as f:
            template_content = f.read()
        
        abs_nc_input_dir = os.path.abspath(nc_input_dir)
        abs_mdv_output_dir = os.path.abspath(mdv_output_dir)
        
        final_params_content = template_content.replace("%%INPUT_DIR%%", abs_nc_input_dir)
        final_params_content = final_params_content.replace("%%OUTPUT_DIR%%", abs_mdv_output_dir)
        
        temp_params_path = "/app/lrose_params/temp.params.final"
        with open(temp_params_path, 'w') as f:
            f.write(final_params_content)

    except Exception as e:
        logging.error(f"No se pudo preparar el archivo de parámetros: {e}")
        return False

    command = ["NcGeneric2Mdv", "-params", temp_params_path, "-start", "2005 01 01 00 00 00", "-end", "2030 12 31 23 59 59"]
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, env=mdv_env)
        logging.info("NcGeneric2Mdv ejecutado exitosamente.")

    except subprocess.CalledProcessError as e:
        logging.error(f"Falló la ejecución de NcGeneric2Mdv. Error: {e.stderr}")
        return False

    # --- 4. Renombrado de Archivos de Salida (LÓGICA CORREGIDA) ---
    logging.info("Renombrando archivos MDV de salida...")
    try:
        # NcGeneric2Mdv crea una estructura de subdirectorios con la fecha (ej: YYYYMMDD/)
        # por lo que buscamos recursivamente.
        generated_files = glob.glob(os.path.join(abs_mdv_output_dir, "**", "*.mdv"), recursive=True)
        
        if not generated_files:
            logging.warning("NcGeneric2Mdv se ejecutó pero no se encontraron archivos .mdv en la salida.")
            return True # No es un error fatal, puede que no hubiera nada que convertir.

        for old_filepath in generated_files:
            filename = os.path.basename(old_filepath)
            
            # Replicamos la lógica de tu script: quitar el prefijo de fecha.
            if "_" in filename:
                # Particiona el string en el primer '_' y toma la segunda parte.
                new_filename = filename.split('_', 1)[1]
                new_filepath = os.path.join(os.path.dirname(old_filepath), new_filename)
                
                logging.info(f"  Renombrando '{filename}' -> '{new_filename}'")
                os.rename(old_filepath, new_filepath)
        return True
    except Exception as e:
        logging.error(f"Ocurrió un error durante el renombrado de archivos: {e}")
        return False

def main():
    """
    Bucle principal con lógica de VENTANA DESLIZANTE.
    """
    logging.info("====== INICIO DEL WORKER DEL PIPELINE (v8 - Sliding Window) ======")
    for path in [MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, MDV_OUTPUT_DIR]:
        os.makedirs(path, exist_ok=True)
    
    predictor = ModelPredictor(MODEL_PATH)
    
    while True:
        try:
            # --- TAREA PRIORITARIA: Procesar UN MDV si existe ---
            mdv_files = sorted([f for f in os.listdir(MDV_INBOX_DIR) if f.endswith('.mdv')])
            if mdv_files:
                mdv_file_to_process = mdv_files[0]
                mdv_path = os.path.join(MDV_INBOX_DIR, mdv_file_to_process)
                
                mdv_to_nc_params = "/app/lrose_params/Mdv2NetCDF.params"
                success = convert_mdv_to_nc(mdv_path, INPUT_DIR, mdv_to_nc_params)
                
                shutil.move(mdv_path, os.path.join(MDV_ARCHIVE_DIR, mdv_file_to_process))
                if success:
                    logging.info(f"{mdv_file_to_process} archivado y convertido.")
                else:
                    logging.warning(f"{mdv_file_to_process} archivado pero falló la conversión.")
                
                time.sleep(1)
                continue     # CLAVE: Vuelve al inicio del bucle para buscar más MDVs

            # --- TAREA SECUNDARIA: buscar secuencias NC ---
            input_files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith('.nc')])
            logging.info(f"VERIFICANDO BUFFER: Se encontraron {len(input_files)} archivos .nc")
            
            if len(input_files) >= SECUENCE_LENGHT:
                
                # --- LÓGICA DE VENTANA DESLIZANTE ---
                # 1. Tomar los ÚLTIMOS 12 archivos de la lista ordenada
                files_to_process = input_files[-SECUENCE_LENGHT:]
                full_paths = [os.path.join(INPUT_DIR, f) for f in files_to_process]
                
                seq_id = os.path.splitext(files_to_process[-1])[0] # Usamos el último como identificador
                update_status(f"Procesando secuencia deslizante terminada en {seq_id}", len(files_to_process), SECUENCE_LENGHT)
                
                # --- La lógica de predicción y guardado que ya tenías ---
                input_tensor = load_and_preprocess_input_sequence(full_paths)
                prediction_tensor = predictor.predict(input_tensor)
                prediction_cleaned = postprocess_prediction(prediction_tensor)
                try:
                    last_input_dt_utc = datetime.strptime(seq_id, '%Y%m%d%H%M%S')
                except ValueError:
                    last_input_dt_utc = datetime.now(timezone.utc)
                
                output_subdir_name = last_input_dt_utc.strftime('%Y%m%d-%H%M%S')
                output_subdir_path = os.path.join(OUTPUT_DIR, output_subdir_name)
                os.makedirs(output_subdir_path, exist_ok=True)
                save_prediction_as_netcdf(output_subdir_path, prediction_cleaned, last_input_dt_utc)
                
                params_template_path = "/app/lrose_params/params.nc2mdv.final"
                convert_predictions_to_mdv(output_subdir_path, MDV_OUTPUT_DIR, params_template_path)
                
                # --- GESTIÓN DEL BUFFER (VENTANA DESLIZANTE) ---
                # En lugar de archivar los 12 archivos usados, archivamos solo los más antiguos
                # para mantener el tamaño del buffer y permitir que la ventana se deslice.
                if len(input_files) > SECUENCE_LENGHT:
                    num_to_archive = len(input_files) - SECUENCE_LENGHT
                    files_to_archive = input_files[:num_to_archive]
                    logging.info(f"Limpiando buffer: archivando {len(files_to_archive)} archivo(s) antiguo(s)...")
                    for f in files_to_archive:
                        path_to_archive = os.path.join(INPUT_DIR, f)
                        shutil.move(path_to_archive, os.path.join(ARCHIVE_DIR, f))
                
                logging.info(f"Ciclo de predicción para la secuencia {seq_id} completado.")

            else:
                update_status("IDLE - Esperando archivos NC", len(input_files), SECUENCE_LENGHT)

            # Si no hay nada que hacer, esperar el intervalo completo
            time.sleep(POLL_INTERVAL_SECONDS)
        
        except Exception as e:
            update_status("ERROR - ver logs para detalles", -1, -1)
            logging.error(f"Ocurrió un error en el bucle principal: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS * 2)

if __name__ == "__main__":
    main()

    
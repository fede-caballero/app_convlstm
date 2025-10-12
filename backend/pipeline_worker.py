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
import pyart
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Importamos desde nuestros módulos
from config import (MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, 
                    SECUENCE_LENGHT, POLL_INTERVAL_SECONDS, MODEL_PATH, 
                    DATA_CONFIG, STATUS_FILE_PATH, MDV_OUTPUT_DIR, IMAGE_OUTPUT_DIR)

def generar_imagen_desde_nc(nc_file_path: str, output_image_path: str, skip_levels: int = 2):
    """
    Genera una imagen de reflectividad compuesta sobre un mapa a partir de un archivo NetCDF.
    """
    try:
        logging.info(f"Generando imagen para: {os.path.basename(nc_file_path)}")
        
        ds = xr.open_dataset(nc_file_path, mask_and_scale=True, decode_times=False)

        lon_name = 'longitude' if 'longitude' in ds.coords else 'x0'
        lat_name = 'latitude' if 'latitude' in ds.coords else 'y0'
        alt_name = 'altitude' if 'altitude' in ds.coords else 'z0'
        
        x = ds[lon_name].values
        y = ds[lat_name].values
        dbz_data = ds['DBZ'].squeeze().values

        # --- 1. Crear el composite omitiendo los primeros niveles ---
        if dbz_data.ndim == 3 and dbz_data.shape[0] > skip_levels:
            composite_data_2d = np.nanmax(dbz_data[skip_levels:, :, :], axis=0)
        else:
            composite_data_2d = np.nanmax(dbz_data, axis=0)

        # --- 2. Obtener la información de la proyección ---
        proj_info = ds['grid_mapping_0'].attrs
        lon_0 = proj_info['longitude_of_projection_origin']
        lat_0 = proj_info['latitude_of_projection_origin']
        projection = ccrs.AzimuthalEquidistant(central_longitude=lon_0, central_latitude=lat_0)

        # --- 3. Creación del gráfico final con mapa ---
        logging.info("Generando gráfico final con mapa...")
        fig = plt.figure(figsize=(12, 12))
        ax = fig.add_subplot(1, 1, 1, projection=projection)

        # Definir la extensión de los datos en metros
        x_min, x_max = x.min() * 1000, x.max() * 1000
        y_min, y_max = y.min() * 1000, y.max() * 1000
        extent = (x_min, x_max, y_min, y_max)

        # Dibujar la imagen de reflectividad en el eje del mapa
        im = ax.imshow(composite_data_2d, cmap='LangRainbow12', origin='lower', 
                       vmin=0, vmax=70, extent=extent)

        # Añadir características del mapa
        ax.add_feature(cfeature.COASTLINE.with_scale('10m'), edgecolor='black', linewidth=0.5)
        ax.add_feature(cfeature.BORDERS.with_scale('10m'), edgecolor='black', linewidth=0.7)
        ax.add_feature(cfeature.STATES.with_scale('10m'), linestyle='--', edgecolor='gray', linewidth=0.5)
        ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

        fig.colorbar(im, ax=ax, label="Reflectividad (dBZ)", shrink=0.7)
        ax.set_title(f"Reflectividad Compuesta - {os.path.basename(nc_file_path)}")
        
        plt.tight_layout()
        plt.savefig(output_image_path, dpi=150)
        plt.close(fig)

        logging.info(f"  -> Imagen final guardada en: {output_image_path}")
        return True

    except Exception as e:
        logging.error(f"No se pudo generar la imagen para {nc_file_path}: {e}", exc_info=True)
        return False
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
    logging.info(f"Max dBZ después de umbral: {np.nanmax(pred_physical_cleaned)}")
    # Quitamos la dimensión de canal que es 1 -> (T_pred, Z, H, W)
    return pred_physical_cleaned.squeeze(2)

def save_prediction_as_netcdf(output_subdir: str, pred_sequence_cleaned: np.ndarray, data_cfg: dict, start_datetime: datetime):
    """
    Guarda la predicción en un archivo NetCDF con todos los metadatos
    necesarios para ser compatible con las herramientas de LROSE.
    """
    # Se usa 'pred_sequence_cleaned' consistentemente
    num_pred_steps, num_z, num_y, num_x = pred_sequence_cleaned.shape
    
    # --- 1. Pre-calcular información de la grilla ---
    z_coords = np.arange(1.0, 1.0 + num_z * 1.0, 1.0, dtype=np.float32)
    x_coords = np.arange(-249.5, -249.5 + num_x * 1.0, 1.0, dtype=np.float32)
    y_coords = np.arange(-249.5, -249.5 + num_y * 1.0, 1.0, dtype=np.float32)
    
    # Se usa 'data_cfg' consistentemente
    proj = pyproj.Proj(
        proj="aeqd",
        lon_0=data_cfg['sensor_longitude'],
        lat_0=data_cfg['sensor_latitude'],
        R=data_cfg['earth_radius_m']
    )
    
    x_grid_m, y_grid_m = np.meshgrid(x_coords * 1000.0, y_coords * 1000.0)
    lon0_grid, lat0_grid = proj(x_grid_m, y_grid_m, inverse=True)

    # Itera y guarda un archivo por cada paso de predicción
    for i in range(num_pred_steps):
        # Se usa 'data_cfg' y 'start_datetime' consistentemente
        lead_time_minutes = (i + 1) * data_cfg.get('prediction_interval_minutes', 3)
        forecast_dt_utc = start_datetime + timedelta(minutes=lead_time_minutes)
        
        # Se usa 'output_subdir' consistentemente
        output_filename = os.path.join(output_subdir, f"{forecast_dt_utc.strftime('%Y%m%d_%H%M%S')}.nc")

        with NCDataset(output_filename, 'w', format='NETCDF3_CLASSIC') as ds_out:
            # --- 2. Escribir metadatos, dimensiones y variables ---
            ds_out.Conventions = "CF-1.6"
            ds_out.title = f"SAN_RAFAEL_PRED - Forecast t+{lead_time_minutes}min"
            ds_out.institution = "UM"
            ds_out.source = "ConvLSTM Model Prediction"
            ds_out.history = f"Created {datetime.now(timezone.utc).isoformat()} by pipeline."
            ds_out.comment = f"Forecast data from model. Lead time: {lead_time_minutes} min."
            ds_out.sensor_longitude = data_cfg['sensor_longitude']
            ds_out.sensor_latitude = data_cfg['sensor_latitude']
            ds_out.sensor_altitude = data_cfg['sensor_altitude_km']

            ds_out.createDimension('time', None)
            ds_out.createDimension('bounds', 2)
            ds_out.createDimension('longitude', num_x)
            ds_out.createDimension('latitude', num_y)
            ds_out.createDimension('altitude', num_z)

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
            
            # Se usa 'data_cfg' consistentemente
            gm_v = ds_out.createVariable('grid_mapping_0', 'i4'); gm_v.setncatts({'grid_mapping_name':"azimuthal_equidistant", 'longitude_of_projection_origin':data_cfg['sensor_longitude'], 'latitude_of_projection_origin':data_cfg['sensor_latitude'], 'false_easting':0.0, 'false_northing':0.0, 'earth_radius':data_cfg['earth_radius_m']})

            # --- Variable Principal DBZ (COMO FLOAT, SIN EMPAQUETAR) ---
            # Basado en el ncdump del archivo que funcionaba localmente.
            _fill_value_float = -999.0
            
            # Los datos ya están en el formato físico correcto (float32) y con NaNs
            # donde los valores son inválidos o están por debajo del umbral.
            prediction_data_for_nc = pred_sequence_cleaned[i]

            # Al crear la variable con un fill_value, netCDF4 reemplazará automáticamente
            # los NaN en el array por este valor al escribirlo.
            dbz_v = ds_out.createVariable('DBZ', 'f4', ('time', 'altitude', 'latitude', 'longitude'), fill_value=_fill_value_float)
            
            # Añadimos los metadatos que vimos en el ncdump funcional
            dbz_v.setncatts({
                'long_name': 'DBZ',
                'standard_name': 'reflectivity',
                'units': 'dBZ',
                'missing_value': _fill_value_float
            })

            dbz_v[0, :, :, :] = prediction_data_for_nc

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
        generated_files = glob.glob(os.path.join(abs_mdv_output_dir, "**", "*.mdv"), recursive=True)
        
        if not generated_files:
            logging.warning("NcGeneric2Mdv se ejecutó pero no se encontraron archivos .mdv en la salida.")
            return True

        # Mapear NC a MDV basado en el timestamp
        nc_files = sorted(glob.glob(os.path.join(abs_nc_input_dir, "*.nc")))
        nc_timestamps = [os.path.basename(f).replace('.nc', '') for f in nc_files]  # e.g., ['20250906_120000', ...]

        for old_filepath in generated_files:
            filename = os.path.basename(old_filepath)  # e.g., '20250906_120000.mdv'
            
            # Preservar el nombre completo (YYYYMMDD_HHMMSS.mdv)
            if filename.endswith('.mdv') and '_' in filename:
                new_filename = filename  # Mantener sin cambios
                new_filepath = os.path.join(os.path.dirname(old_filepath), new_filename)
                
                # Verificar que el timestamp coincide con un NC
                timestamp = filename.replace('.mdv', '')
                if timestamp in nc_timestamps:
                    logging.info(f"  Manteniendo nombre MDV: '{filename}'")
                    if old_filepath != new_filepath:
                        os.rename(old_filepath, new_filepath)
                else:
                    logging.warning(f"  MDV '{filename}' no tiene NC correspondiente. Manteniendo nombre.")
            else:
                logging.warning(f"  Formato inesperado para '{filename}'. Manteniendo nombre.")
                
        return True
    except Exception as e:
        logging.error(f"Ocurrió un error durante el renombrado de archivos: {e}")
        return False

def main():
    """
    Bucle principal con lógica de VENTANA DESLIZANTE.
    """
    logging.info("====== INICIO DEL WORKER DEL PIPELINE (v9 - Image Generation) ======")
    # Aseguramos que todos los directorios necesarios existan
    for path in [MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, MDV_OUTPUT_DIR, IMAGE_OUTPUT_DIR]:
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
                
                # Archivamos el MDV original independientemente del resultado de la conversión
                archive_mdv_path = os.path.join(MDV_ARCHIVE_DIR, os.path.basename(mdv_path))
                shutil.move(mdv_path, archive_mdv_path)

                if success:
                    logging.info(f"{mdv_file_to_process} archivado y convertido a NC.")
                else:
                    logging.warning(f"{mdv_file_to_process} archivado, pero la conversión a NC falló.")
                
                time.sleep(1) # Pequeña pausa para no saturar el CPU
                continue     # Vuelve al inicio para priorizar la conversión de MDVs

            # --- TAREA SECUNDARIA: buscar secuencias NC ---
            input_files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith('.nc')])
            
            if len(input_files) < SECUENCE_LENGHT:
                update_status("IDLE - Esperando archivos NC", len(input_files), SECUENCE_LENGHT)
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            # --- INICIO DEL CICLO DE PREDICCIÓN ---
            files_to_process = input_files[-SECUENCE_LENGHT:]
            full_paths = [os.path.join(INPUT_DIR, f) for f in files_to_process]
            
            seq_id = os.path.splitext(files_to_process[-1])[0]
            update_status(f"Procesando secuencia terminada en {seq_id}", len(files_to_process), SECUENCE_LENGHT)
            
            # --- 1. Generar imagen del último scan de entrada ---
            last_input_nc_path = full_paths[-1]
            input_image_filename = f"INPUT_{seq_id}.png"
            input_image_path = os.path.join(IMAGE_OUTPUT_DIR, input_image_filename)
            generar_imagen_desde_nc(last_input_nc_path, input_image_path, skip_levels=2)

            # --- 2. Predecir ---
            input_tensor = load_and_preprocess_input_sequence(full_paths)
            prediction_tensor = predictor.predict(input_tensor)
            prediction_cleaned = postprocess_prediction(prediction_tensor)
            
            try:
                last_input_dt_utc = datetime.strptime(seq_id, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            except ValueError:
                last_input_dt_utc = datetime.now(timezone.utc)
            
            # --- 3. Guardar predicciones en NetCDF ---
            output_subdir_name = last_input_dt_utc.strftime('%Y%m%d-%H%M%S')
            output_subdir_path = os.path.join(OUTPUT_DIR, output_subdir_name)
            os.makedirs(output_subdir_path, exist_ok=True)
            save_prediction_as_netcdf(output_subdir_path, prediction_cleaned, DATA_CONFIG, last_input_dt_utc)

            # --- 4. Convertir predicciones a MDV (para Titan) ---
            params_template_path = "/app/lrose_params/params.nc2mdv.final"
            convert_predictions_to_mdv(output_subdir_path, MDV_OUTPUT_DIR, params_template_path)

            # --- 5. Generar imágenes de las predicciones ---
            logging.info("Iniciando generación de imágenes de predicción...")
            prediction_nc_files = sorted(glob.glob(os.path.join(output_subdir_path, "*.nc")))
            for nc_file in prediction_nc_files:
                pred_filename_base = os.path.splitext(os.path.basename(nc_file))[0]
                pred_image_filename = f"PRED_{pred_filename_base}.png"
                pred_image_path = os.path.join(IMAGE_OUTPUT_DIR, pred_image_filename)
                generar_imagen_desde_nc(nc_file, pred_image_path, skip_levels=2)

            # --- 6. Gestión del buffer (Ventana deslizante) ---
            oldest_file_in_sequence = files_to_process[0]
            path_to_archive = os.path.join(INPUT_DIR, oldest_file_in_sequence)
            logging.info(f"Ventana deslizante: archivando '{oldest_file_in_sequence}' para esperar el próximo escaneo.")
            shutil.move(path_to_archive, os.path.join(ARCHIVE_DIR, oldest_file_in_sequence))
            
            logging.info(f"Ciclo de predicción para la secuencia {seq_id} completado.")

            # Pequeña pausa después de un ciclo completo
            time.sleep(1)

        except Exception as e:
            update_status("ERROR - ver logs para detalles", -1, -1)
            logging.error(f"Ocurrió un error en el bucle principal: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS * 2)

if __name__ == "__main__":
    main()

    
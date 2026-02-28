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
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import cartopy.crs as ccrs
import sqlite3
from scipy.ndimage import label, center_of_mass


# Importamos desde nuestros módulos
from config import (MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, 
                    SECUENCE_LENGHT, POLL_INTERVAL_SECONDS, MODEL_PATH, 
                    DATA_CONFIG, STATUS_FILE_PATH, MDV_OUTPUT_DIR, IMAGE_OUTPUT_DIR, DB_PATH,
                    VAPID_PRIVATE_KEY, VAPID_CLAIM_EMAIL, FRONTEND_URL)
from model.predict import ModelPredictor
import aircraft_tracker

from pywebpush import webpush, WebPushException
try:
    from py_vapid import Vapid
except ImportError:
    logging.error("Could not import Vapid from py_vapid")
    Vapid = None

# --- Utilitarios ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of earth in km
    dLat = np.radians(lat2 - lat1)
    dLon = np.radians(lon2 - lon1)
    a = np.sin(dLat/2) * np.sin(dLat/2) + \
        np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * \
        np.sin(dLon/2) * np.sin(dLon/2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    d = R * c # Distance in km
    return d


# --- Configuración del Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def detect_storm_cells(dbz_data, x_vals, y_vals, projection):
    """
    Detecta celdas de tormenta (>50 dBZ) y calcula sus centroides.
    Clasificación:
      - > 50 dBZ: Lluvia Torrencial
      - > 55 dBZ: Probable Granizo
      - > 58 dBZ: Granizo / Lluvia Torrencial Extrema
    """
    cells = []
    # Thresholding: Solo interesa > 50 dBZ
    mask = dbz_data > 50.0
    
    if not np.any(mask):
        return []

    # Connected Components
    labeled_array, num_features = label(mask)
    
    geo_proj = ccrs.Geodetic()

    for label_idx in range(1, num_features + 1):
        # Mask para esta celda
        cell_mask = (labeled_array == label_idx)
        
        # Max dBZ en la celda
        max_dbz = float(np.max(dbz_data[cell_mask]))
        
        # Clasificación
        hazard_type = "Lluvia Torrencial"
        if max_dbz > 58:
            hazard_type = "Granizo Confirmado"
        elif max_dbz > 55:
            hazard_type = "Probable Granizo"
            
        # Centroide (Weighted by intensity could be better, but geometric is simpler/faster)
        # Coordinates in array indices (y, x)
        cy, cx = center_of_mass(cell_mask)
        
        # Convertir indices a coordenadas proyectadas (metros/km)
        # Asumimos que x_vals y y_vals coinciden con los índices
        # Interpolación simple:
        # x_val = x_vals[int(cx)] (aprox) o interpolado
        
        # Usamos int para simplificar, ya que la resolución es ~1km
        px_x = int(round(cx))
        px_y = int(round(cy))
        
        # Bounds check
        px_x = max(0, min(px_x, len(x_vals) - 1))
        px_y = max(0, min(px_y, len(y_vals) - 1))
        
        real_x = x_vals[px_x] * 1000 # a metros
        real_y = y_vals[px_y] * 1000 # a metros
        
        # Transformar a Lat/Lon
        geo_point = geo_proj.transform_point(real_x, real_y, projection)
        lon, lat = geo_point[0], geo_point[1]
        
        cells.append({
            "type": hazard_type,
            "max_dbz": round(max_dbz, 1),
            "lat": round(lat, 5),
            "lon": round(lon, 5)
        })
        
    return cells

def check_proximity_alerts(storm_cells):
    """
    Verifica si hay usuarios cerca (< 20km) de alguna celda de tormenta.
    Envía notificación si no se ha enviado una en los últimos 10 minutos.
    """
    if not storm_cells:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Get Users with Location and Push Subscriptions
        # We join to ensure they have a subscription
        cursor.execute("""
            SELECT DISTINCT u.id, s.latitude, s.longitude, u.last_proximity_alert, 
                   s.endpoint, s.p256dh, s.auth
            FROM users u
            JOIN push_subscriptions s ON u.id = s.user_id
            WHERE s.latitude IS NOT NULL 
              AND s.longitude IS NOT NULL
              AND s.alert_proximity = 1
        """)
        users_subs = cursor.fetchall()
        
        if not users_subs:
            return

        # Prepare VAPID
        vapid_obj = None
        if Vapid and VAPID_PRIVATE_KEY:
             try:
                 key_bytes = VAPID_PRIVATE_KEY.encode('utf-8')
                 vapid_obj = Vapid.from_pem(key_bytes)
             except Exception as e:
                 logging.error(f"Worker VAPID Setup Error: {e}")
                 # Continue without VAPID? Usually strictly required. 
                 pass

        now = datetime.now(timezone.utc)
        
        # Keep track of sent alerts to avoid double sending if user has multiple devices
        # actually the loop is per subscription (device), so it's fine.
        # But we update user.last_proximity_alert ONCE per user?
        # Better: check user cooldown.
        
        users_processed = {} # userId -> sent?

        for row in users_subs:
            user_id, u_lat, u_lon, last_alert_iso, endpoint, p256dh, auth_key = row
            
            # Check Cooldown (10 mins)
            if last_alert_iso:
                try:
                    last_alert = datetime.fromisoformat(last_alert_iso)
                    if (now - last_alert).total_seconds() < 600: # 10 mins
                        continue 
                except:
                    pass # Invalid date, proceed
            
            # Check Distance to ANY cell
            min_dist = float('inf')
            nearest_cell = None
            
            for cell in storm_cells:
                dist = haversine(u_lat, u_lon, cell['lat'], cell['lon'])
                if dist < min_dist:
                    min_dist = dist
                    nearest_cell = cell
            
            # Threshold: 20km
            if min_dist < 20 and nearest_cell:
                # SEND ALERT!
                msg = f"Detectada {nearest_cell['type']} a {int(min_dist)}km de tu ubicación."
                
                logging.info(f"Sending Proximity Alert to User {user_id}: {msg}")
                
                # Payload
                notification_data = json.dumps({
                    "title": "¡Tormenta Cercana!",
                    "body": msg,
                    "url": "/", # Open Map
                    "icon": "/icon-192x192.png"
                })
                
                # Push Logic (Duplicate from API, should be refactored but okay for now)
                subscription_info = {
                    "endpoint": endpoint,
                    "keys": {"p256dh": p256dh, "auth": auth_key}
                }
                
                try:
                    headers = {"TTL": "60", "Urgency": "high"}
                    auth_headers = {}
                    if vapid_obj and hasattr(vapid_obj, "get_authorization_header"):
                         header_value = vapid_obj.get_authorization_header(endpoint, VAPID_CLAIM_EMAIL)
                         if isinstance(header_value, (bytes, str)):
                             if isinstance(header_value, bytes):
                                 header_value = header_value.decode('utf-8')
                             auth_headers = {"Authorization": header_value}
                         elif isinstance(header_value, dict):
                             auth_headers = header_value
                    elif vapid_obj:
                         from urllib.parse import urlparse
                         parsed = urlparse(endpoint)
                         aud = f"{parsed.scheme}://{parsed.netloc}"
                         claim = {"aud": aud, "sub": VAPID_CLAIM_EMAIL}
                         token = vapid_obj.sign(claim)
                         if isinstance(token, dict):
                             auth_headers = token
                         else:
                             if isinstance(token, bytes):
                                 token = token.decode('utf-8')
                             if "vapid t=" in token:
                                 auth_headers = {"Authorization": token}
                             else:
                                 auth_headers = {"Authorization": f"WebPush {token}"}
                    
                    headers.update(auth_headers)
                    
                    webpush(
                        subscription_info=subscription_info,
                        data=notification_data,
                        vapid_private_key=None,
                        vapid_claims=None,
                        headers=headers
                    )
                    
                    # Mark user as updated (in memory for this loop)
                    if user_id not in users_processed:
                        # Update DB timestamp
                        cursor.execute("UPDATE users SET last_proximity_alert = ? WHERE id = ?", (now.isoformat(), user_id))
                        conn.commit()
                        users_processed[user_id] = True
                        
                except Exception as e:
                    logging.error(f"Worker Push Error: {e}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in check_proximity_alerts: {e}")

def check_and_send_aircraft_alerts(sent_aircraft_alerts):
    """
    Verifica si hay aviones antigranizo en el tracking y envía push a quienes lo solicitaron.
    Usa un diccionario en memoria para no spamear (cooldown de 4 horas por avión).
    """
    try:
        data = aircraft_tracker.get_aircraft_data()
        if not data:
            return

        now = datetime.now(timezone.utc)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get users interested in aircraft alerts
        cursor.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE alert_aircraft = 1")
        subscriptions = cursor.fetchall()
        
        if not subscriptions:
            conn.close()
            return

        # Prepare VAPID
        vapid_obj = None
        if Vapid and VAPID_PRIVATE_KEY:
            try:
                vapid_obj = Vapid.from_pem(VAPID_PRIVATE_KEY.encode('utf-8'))
            except Exception:
                pass

        for ac in data:
            reg = ac.get("reg") or ac.get("callsign", "Desconocido")
            
            # Check if we already alerted for this aircraft recently (4 hours cooldown)
            last_alert_time = sent_aircraft_alerts.get(reg)
            if last_alert_time and (now - last_alert_time).total_seconds() < 14400:
                continue
                
            logging.info(f"New aircraft flight detected: {reg}. Sending alerts...")
            sent_aircraft_alerts[reg] = now
            
            notification_data = json.dumps({
                "title": "¡Avión Antigranizo!",
                "body": f"✈️ Avión en vuelo ({reg}) detectado en el radar.",
                "url": "/",
                "icon": "/icon-192x192.png"
            })

            headers = {"TTL": "60", "Urgency": "high"}
            for sub in subscriptions:
                endpoint, p256dh, auth_key = sub
                try:
                    sub_headers = headers.copy()
                    auth_headers = {}
                    if vapid_obj and hasattr(vapid_obj, "get_authorization_header"):
                         header_value = vapid_obj.get_authorization_header(endpoint, VAPID_CLAIM_EMAIL)
                         if isinstance(header_value, (bytes, str)):
                             if isinstance(header_value, bytes):
                                 header_value = header_value.decode('utf-8')
                             auth_headers = {"Authorization": header_value}
                         elif isinstance(header_value, dict):
                             auth_headers = header_value
                    elif vapid_obj:
                         from urllib.parse import urlparse
                         parsed = urlparse(endpoint)
                         aud = f"{parsed.scheme}://{parsed.netloc}"
                         claim = {"aud": aud, "sub": VAPID_CLAIM_EMAIL}
                         token = vapid_obj.sign(claim)
                         if isinstance(token, dict):
                             auth_headers = token
                         else:
                             if isinstance(token, bytes):
                                 token = token.decode('utf-8')
                             if "vapid t=" in token:
                                 auth_headers = {"Authorization": token}
                             else:
                                 auth_headers = {"Authorization": f"WebPush {token}"}
                    
                    sub_headers.update(auth_headers)
                    
                    webpush(
                        subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth_key}},
                        data=notification_data,
                        vapid_private_key=None,
                        vapid_claims=None,
                        headers=sub_headers
                    )
                except Exception as e:
                    logging.error(f"Aircraft Push Error: {e}")
                    
        conn.close()
    except Exception as e:
        logging.error(f"Error checking aircraft alerts: {e}")

def generar_imagen_transparente_y_bounds(nc_file_path: str, output_image_path: str, skip_levels: int = 2):
    """
    Genera una imagen transparente de reflectividad compuesta y devuelve sus coordenadas geográficas.
    """
    try:
        logging.info(f"Generando imagen transparente para: {os.path.basename(nc_file_path)}")
        
        ds = xr.open_dataset(nc_file_path, mask_and_scale=True, decode_times=False)

        lon_name = 'longitude' if 'longitude' in ds.coords else 'x0'
        lat_name = 'latitude' if 'latitude' in ds.coords else 'y0'
        
        x = ds[lon_name].values
        y = ds[lat_name].values
        dbz_data = ds['DBZ'].squeeze().values

        # --- 1. Crear el composite ---
        if dbz_data.ndim == 3:
            if dbz_data.shape[0] > skip_levels:
                composite_data_2d = np.nanmax(dbz_data[skip_levels:, :, :], axis=0)
            else:
                 composite_data_2d = np.nanmax(dbz_data, axis=0)
        elif dbz_data.ndim == 2:
            # Ya es 2D (caso predicciones)
            composite_data_2d = dbz_data
        else:
            logging.error(f"Dimensiones inesperadas en {nc_file_path}: {dbz_data.ndim}")
            return None

        # --- 2. Obtener la información de la proyección ---
        proj_info = ds['grid_mapping_0'].attrs
        lon_0 = proj_info['longitude_of_projection_origin']
        lat_0 = proj_info['latitude_of_projection_origin']
        projection = ccrs.AzimuthalEquidistant(central_longitude=lon_0, central_latitude=lat_0)

        # --- 3. Creación del gráfico transparente (TITAN Color Scale) ---
        fig = plt.figure(figsize=(10, 10), dpi=150)
        ax = fig.add_subplot(1, 1, 1)
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        ax.set_axis_off()

        # Configuración de Colores TITAN
        titan_bounds = [5, 10, 20, 30, 35, 36, 39, 42, 45, 48, 51, 54, 57, 60, 65, 70, 80]
        titan_colors = [
            '#483d8b', # 5-10
            '#005a00', # 10-20
            '#007000', # 20-30
            '#087fdb', # 30-35
            '#1c47e8', # 35-36
            '#6e0dc6', # 36-39
            '#c80f86', # 39-42
            '#c06487', # 42-45
            '#d2883b', # 45-48
            '#fac431', # 48-51
            '#fefa03', # 51-54
            '#fe9a58', # 54-57
            '#fe5f05', # 57-60
            '#fd341c', # 60-65
            '#bebebe', # 65-70
            '#d3d3d3'  # 70-80
        ]
        cmap = ListedColormap(titan_colors)
        cmap.set_under('none') # Transparente por debajo de 5 dbz
        norm = BoundaryNorm(titan_bounds, cmap.N)

        # Dibujar la imagen de reflectividad CON CONTORNOS SUAVIZADOS (Vector-like)
        # En lugar de píxeles (imshow), usamos contourf para bordes definidos pero curvos.
        
        # Niveles explícitos para que coincidan con la escala TITAN
        # levels = [20, 30, 40, 50, 60, 70, 80] <-- REMOVED HARDCODED
        levels = titan_bounds 
        
        # Usamos contourf. 
        # extend='max' para que valores >80 sigan siendo grises.
        # antialiased=True para bordes suaves.
        ax.contourf(x, y, composite_data_2d, levels=levels, cmap=cmap, norm=norm, extend='max', antialiased=True)
        
        plt.tight_layout(pad=0)
        # Aumentamos DPI a 300 para que los contornos se vean nítidos en móviles retina/high-res
        plt.savefig(output_image_path, dpi=300, transparent=True, bbox_inches='tight', pad_inches=0)
        plt.close(fig)

        # --- 4. Calcular Bounding Box Geográfico ---
        x_min, x_max = x.min() * 1000, x.max() * 1000
        y_min, y_max = y.min() * 1000, y.max() * 1000
        
        # Convertir las esquinas de metros a lat/lon
        geo_proj = ccrs.Geodetic()
        sw_corner = geo_proj.transform_point(x_min, y_min, projection)
        ne_corner = geo_proj.transform_point(x_max, y_max, projection)
        
        bounds = [[float(sw_corner[1]), float(sw_corner[0])], [float(ne_corner[1]), float(ne_corner[0])]] # Formato: [[lat_min, lon_min], [lat_max, lon_max]]

        # --- 5. Detectar Celdas y Centroides ---
        storm_cells = detect_storm_cells(composite_data_2d, x, y, projection)
        
        # --- 6. Verificar Alertas de Proximidad ---
        check_proximity_alerts(storm_cells)

        logging.info(f"  -> Imagen transparente guardada en: {output_image_path}")
        logging.info(f"  -> Coordenadas calculadas: {bounds}")
        logging.info(f"  -> Celdas detectadas: {len(storm_cells)}")
        
        return bounds, storm_cells

    except Exception as e:
        logging.error(f"No se pudo generar la imagen para {nc_file_path}: {e}", exc_info=True)
        return None

from database import init_db, DB_PATH

def log_prediction(timestamp, input_seq_id, output_path, status="SUCCESS"):
    """Registra una predicción en la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO predictions (timestamp, input_sequence_id, output_path, status)
            VALUES (?, ?, ?, ?)
        ''', (timestamp.isoformat(), input_seq_id, output_path, status))
        conn.commit()
        conn.close()
        logging.info(f"Predicción registrada en DB: {input_seq_id}")
    except Exception as e:
        logging.error(f"Error al registrar en DB: {e}")


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
    """
    Carga secuencia, preprocesa (Max Projection 3D->2D) y hace DOWNSAMPLING (500->250).
    """
    frames = []
    min_dbz = DATA_CONFIG['min_dbz']
    max_dbz = DATA_CONFIG['max_dbz']
    target_height = 250 # Resolución del modelo
    target_width = 250

    for file_path in input_file_paths:
        try:
            with xr.open_dataset(file_path, mask_and_scale=True, decode_times=False) as ds:
                # Fallback variable name
                var_name = DATA_CONFIG.get('variable_name', 'DBZ')
                if var_name not in ds:
                    var_name = list(ds.data_vars)[0]
                data = ds[var_name].values
            
            # Convert to Tensor
            data = torch.from_numpy(data).float()
            
            # 1. Handle NaNs IMMEDIATELY (Same as training)
            data = torch.nan_to_num(data, nan=min_dbz)
            
            # 2. Dimension Reduction (Max Projection)
            while data.ndim > 2:
                if data.shape[0] == 1:
                    data = data.squeeze(0)
                else:
                    data = torch.max(data, dim=0)[0] # Max Composite
            
            # Ensure (1, H, W) -> Channel dim
            if data.ndim == 2:
                data = data.unsqueeze(0)
                
            # 3. Clip & Normalize
            data = torch.clamp(data, min=min_dbz, max=max_dbz)
            data = (data - min_dbz) / (max_dbz - min_dbz)
            
            # 4. Resize (500 -> 250)
            if data.shape[1] != target_height or data.shape[2] != target_width:
                data = torch.nn.functional.interpolate(
                    data.unsqueeze(0),
                    size=(target_height, target_width),
                    mode='bilinear',
                    align_corners=False
                ).squeeze(0)
            
            frames.append(data)
            
        except Exception as e:
            logging.error(f"Error procesando archivo {file_path}: {e}")
            # En producción, o saltamos o rellenamos con ceros. Rellenar es más seguro para no romper batch.
            frames.append(torch.zeros((1, target_height, target_width)))

    # Stack Time: (Seq, C, H, W)
    full_sequence = torch.stack(frames, dim=0)
    # Add Batch: (B, Seq, C, H, W) -> Esto lo hace el caller, pero run_inference devuelve (1, Seq, C, H, W)
    # Pipeline espera (Seq, C, H, W) porque Predictor agrega batch dimension? 
    # Revisemos predict.py: predict(input_volume). input_volume es (Z, T, H, W, C) <- ESTO ES VIEJO.
    # El nuevo modelo espera (B, T, C, H, W).
    return full_sequence.unsqueeze(0) # (1, Seq, C, H, W)

def postprocess_prediction(prediction_norm: torch.Tensor) -> np.ndarray:
    """
    Aplica Upsampling (250->500), desnormalización y umbral físico.
    Entrada: (1, T, C, 250, 250)
    Salida: (T, C, 500, 500) numpy array
    """
    # 1. Upsampling (250 -> 500)
    b, t, c, h, w = prediction_norm.shape
    # Flatten T into B for interpolation
    pred_reshaped = prediction_norm.view(b * t, c, h, w)
    
    pred_upsampled = torch.nn.functional.interpolate(
        pred_reshaped, 
        size=(500, 500), 
        mode='bicubic', # Bicubic para mejor calidad visual
        align_corners=False
    )
    
    # Restore shape: (B, T, C, 500, 500)
    pred_upsampled = pred_upsampled.view(b, t, c, 500, 500)

    # 2. Denormalize
    output_np = pred_upsampled.cpu().numpy()
    pred_physical_raw = output_np * (DATA_CONFIG['max_dbz'] - DATA_CONFIG['min_dbz']) + DATA_CONFIG['min_dbz']
    pred_physical_clipped = np.clip(pred_physical_raw, DATA_CONFIG['min_dbz'], DATA_CONFIG['max_dbz'])
    
    pred_physical_cleaned = pred_physical_clipped.copy()

    # 3. Clean Noise
    threshold = DATA_CONFIG.get('physical_threshold_dbz', 30.0)
    pred_physical_cleaned[pred_physical_cleaned < threshold] = np.nan
    
    # Remove batch dim: (1, T, C, H, W) -> (T, C, H, W)
    # C=1 (Composite). Post-processing logic expects this.
    return pred_physical_cleaned[0]

def save_prediction_as_netcdf(output_subdir: str, pred_sequence_cleaned: np.ndarray, data_cfg: dict, start_datetime: datetime):
    # entrada: (T, C, 500, 500). C=1
    num_pred_steps, num_c, num_y, num_x = pred_sequence_cleaned.shape
    num_z = 1 # Force 1 level (Max Projection)
    
    # --- Grid Preparation ---
    x_coords = np.arange(-249.5, -249.5 + num_x * 1.0, 1.0, dtype=np.float32)
    y_coords = np.arange(-249.5, -249.5 + num_y * 1.0, 1.0, dtype=np.float32)
    z_coords = np.array([1.0], dtype=np.float32)

    proj = pyproj.Proj(
        proj="aeqd", 
        lon_0=data_cfg['sensor_longitude'], 
        lat_0=data_cfg['sensor_latitude'], 
        R=data_cfg['earth_radius_m']
    )
    x_grid_m, y_grid_m = np.meshgrid(x_coords * 1000.0, y_coords * 1000.0)
    lon0_grid, lat0_grid = proj(x_grid_m, y_grid_m, inverse=True)

    for i in range(num_pred_steps):
        lead_time_minutes = (i + 1) * data_cfg.get('prediction_interval_minutes', 3)
        forecast_dt_utc = start_datetime + timedelta(minutes=lead_time_minutes)
        
        file_ts = forecast_dt_utc.strftime("%Y%m%d_%H%M%S")
        output_filename = os.path.join(output_subdir, f"{file_ts}.nc")

        with NCDataset(output_filename, 'w', format='NETCDF3_CLASSIC') as ds_out:
            # --- Global Attributes ---
            ds_out.Conventions = "CF-1.6"
            ds_out.title = f"SAN_RAFAEL_PRED - Forecast t+{lead_time_minutes}min"
            ds_out.institution = "UM"
            ds_out.source = "ConvLSTM Model Prediction"
            ds_out.history = f"Created {datetime.now(timezone.utc).isoformat()} by pipeline."
            ds_out.comment = f"Forecast 2D (Max Projection). Lead time: {lead_time_minutes} min."

            # --- Dimensions ---
            ds_out.createDimension('time', None)
            ds_out.createDimension('bounds', 2)
            ds_out.createDimension('longitude', num_x)
            ds_out.createDimension('latitude', num_y)
            ds_out.createDimension('altitude', num_z)

            # --- Variables ---
            time_value = (forecast_dt_utc.replace(tzinfo=timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
            time_v = ds_out.createVariable('time', 'f8', ('time',))
            time_v.standard_name = "time"; time_v.axis = "T"
            time_v.units = "seconds since 1970-01-01T00:00:00Z"
            time_v[:] = [time_value]

            x_v = ds_out.createVariable('longitude', 'f4', ('longitude',))
            x_v.standard_name = "projection_x_coordinate"; x_v.units = "km"; x_v.axis = "X"
            x_v[:] = x_coords

            y_v = ds_out.createVariable('latitude', 'f4', ('latitude',))
            y_v.standard_name = "projection_y_coordinate"; y_v.units = "km"; y_v.axis = "Y"
            y_v[:] = y_coords

            z_v = ds_out.createVariable('altitude', 'f4', ('altitude',))
            z_v.standard_name = "altitude"; z_v.units = "km"; z_v.axis = "Z"; z_v.positive = "up"
            z_v[:] = z_coords

            lat0_v = ds_out.createVariable('lat0', 'f4', ('latitude', 'longitude',))
            lat0_v.standard_name = "latitude"; lat0_v.units = "degrees_north"
            lat0_v[:] = lat0_grid

            lon0_v = ds_out.createVariable('lon0', 'f4', ('latitude', 'longitude',))
            lon0_v.standard_name = "longitude"; lon0_v.units = "degrees_east"
            lon0_v[:] = lon0_grid

            gm_v = ds_out.createVariable('grid_mapping_0', 'i4')
            gm_v.grid_mapping_name = "azimuthal_equidistant"
            gm_v.longitude_of_projection_origin = data_cfg['sensor_longitude']
            gm_v.latitude_of_projection_origin = data_cfg['sensor_latitude']
            gm_v.false_easting = 0.0; gm_v.false_northing = 0.0
            gm_v.earth_radius = data_cfg['earth_radius_m']

            # --- Data Variable (Single Level) ---
            fill_value_float = np.float32(-999.0)
            dbz_v = ds_out.createVariable('DBZ', 'f4', ('time', 'altitude', 'latitude', 'longitude'), fill_value=fill_value_float)
            dbz_v.units = "dBZ"; dbz_v.standard_name = "reflectivity"
            dbz_v.grid_mapping = "grid_mapping_0"
            dbz_v.coordinates = "lat0 lon0"
            
            # Get 2D frame: (C, H, W) -> C=1
            pred_2d = pred_sequence_cleaned[i] # (1, 500, 500)
            
            # Expand to (1, 1, Y, X) for saving
            pred_final = pred_2d[np.newaxis, :, :, :] 
            
            data_final = np.nan_to_num(pred_final, nan=fill_value_float)
            
            dbz_v[:] = data_final

        logging.info(f"  -> Predicción guardada en: {os.path.basename(output_filename)}")

def convert_mdv_to_nc(mdv_filepath: str, final_output_dir: str, params_path: str):
    mdv_filename = os.path.basename(mdv_filepath)
    logging.info(f"Iniciando conversión de {mdv_filename}...")
    temp_work_dir = "/app/temp_conversion_workspace"
    if os.path.exists(temp_work_dir):
        shutil.rmtree(temp_work_dir)
    os.makedirs(temp_work_dir)
    original_dir = os.getcwd()
    os.chdir(temp_work_dir)
    try:
        command = ["Mdv2NetCDF", "-params", params_path, "-f", os.path.abspath(mdv_filepath)]
        logging.info(f"Ejecutando comando: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        search_path = os.path.join(temp_work_dir, "netCDF", "*.nc")
        nc_files_found = glob.glob(search_path)
        if not nc_files_found:
            logging.error("Conversión reportó éxito, pero no se encontró ningún archivo .nc.")
            return False
        created_nc_path = nc_files_found[0]
        base_nc_name = os.path.basename(created_nc_path)
        try:
            parts = base_nc_name.replace('ncfdata', '').replace('.nc', '').split('_')
            final_filename = f"{parts[0]}{parts[1]}.nc"
        except IndexError:
            logging.warning(f"No se pudo parsear el nombre '{base_nc_name}'. Usando nombre original.")
            final_filename = base_nc_name
        final_nc_path = os.path.join(final_output_dir, final_filename)
        logging.info(f"Moviendo y renombrando '{base_nc_name}' a '{final_nc_path}'")
        shutil.move(created_nc_path, final_nc_path)
        logging.info("Conversión y limpieza completadas exitosamente.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Falló la conversión de {mdv_filename}. Error de LROSE: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error("Error crítico: 'Mdv2NetCDF' no se encontró.")
        return False
    finally:
        os.chdir(original_dir)
        if os.path.exists(temp_work_dir):
            shutil.rmtree(temp_work_dir)

def convert_predictions_to_mdv(nc_input_dir: str, mdv_output_dir: str, params_template_path: str):
    logging.info(f"Iniciando conversión de NetCDF en '{nc_input_dir}' a MDV en '{mdv_output_dir}'")
    mdv_env = os.environ.copy()
    mdv_env["MDV_WRITE_FORMAT"] = "FORMAT_MDV"
    try:
        with open(params_template_path, 'r') as f:
            template_content = f.read()
        abs_nc_input_dir = os.path.abspath(nc_input_dir)
        abs_mdv_output_dir = os.path.abspath(mdv_output_dir)
        final_params_content = template_content.replace("%%INPUT_DIR%%", abs_nc_input_dir).replace("%%OUTPUT_DIR%%", abs_mdv_output_dir)
        temp_params_path = "/app/lrose_params/temp.params.final"
        with open(temp_params_path, 'w') as f:
            f.write(final_params_content)
    except Exception as e:
        logging.error(f"No se pudo preparar el archivo de parámetros: {e}")
        return False
    command = ["NcGeneric2Mdv", "-params", temp_params_path, "-start", "2005 01 01 00 00 00", "-end", "2030 12 31 23 59 59"]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, env=mdv_env)
        logging.info("NcGeneric2Mdv ejecutado exitosamente.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Falló la ejecución de NcGeneric2Mdv. Error: {e.stderr}")
        return False
    logging.info("Renombrando archivos MDV de salida...")
    try:
        generated_files = glob.glob(os.path.join(abs_mdv_output_dir, "**", "*.mdv"), recursive=True)
        if not generated_files:
            logging.warning("NcGeneric2Mdv se ejecutó pero no se encontraron archivos .mdv en la salida.")
            return True
        nc_files = sorted(glob.glob(os.path.join(abs_nc_input_dir, "*.nc")))
        nc_timestamps = [os.path.basename(f).replace('.nc', '') for f in nc_files]
        for old_filepath in generated_files:
            filename = os.path.basename(old_filepath)
            if filename.endswith('.mdv') and '_' in filename:
                new_filename = filename
                new_filepath = os.path.join(os.path.dirname(old_filepath), new_filename)
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
    logging.info("====== INICIO DEL WORKER DEL PIPELINE (v10 - Transparent Images) ======")
    for path in [MDV_INBOX_DIR, MDV_ARCHIVE_DIR, INPUT_DIR, OUTPUT_DIR, ARCHIVE_DIR, MDV_OUTPUT_DIR, IMAGE_OUTPUT_DIR]:
        os.makedirs(path, exist_ok=True)
    
    init_db()
    
    predictor = ModelPredictor(MODEL_PATH)

    sent_aircraft_alerts = {}
    last_aircraft_check = 0
    
    while True:
        try:
            # Polling aircraft telemetry independent of MDV files pacing
            now_ts = time.time()
            if now_ts - last_aircraft_check >= 60: # Check every minute
                check_and_send_aircraft_alerts(sent_aircraft_alerts)
                last_aircraft_check = now_ts
                
            mdv_files = sorted([f for f in os.listdir(MDV_INBOX_DIR) if f.endswith('.mdv')])
            if mdv_files:
                mdv_file_to_process = mdv_files[0]
                mdv_path = os.path.join(MDV_INBOX_DIR, mdv_file_to_process)
                mdv_to_nc_params = "/app/lrose_params/Mdv2NetCDF.params"
                success = convert_mdv_to_nc(mdv_path, INPUT_DIR, mdv_to_nc_params)
                archive_mdv_path = os.path.join(MDV_ARCHIVE_DIR, os.path.basename(mdv_path))
                shutil.move(mdv_path, archive_mdv_path)
                if success:
                    logging.info(f"{mdv_file_to_process} archivado y convertido a NC.")
                else:
                    logging.warning(f"{mdv_file_to_process} archivado, pero la conversión a NC falló.")
                time.sleep(1)
                continue

            input_files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith('.nc')])
            if len(input_files) < SECUENCE_LENGHT:
                update_status("IDLE - Esperando archivos NC", len(input_files), SECUENCE_LENGHT)
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            files_to_process = input_files[-SECUENCE_LENGHT:]
            full_paths = [os.path.join(INPUT_DIR, f) for f in files_to_process]
            seq_id = os.path.splitext(files_to_process[-1])[0]
            update_status(f"Procesando secuencia terminada en {seq_id}", len(files_to_process), SECUENCE_LENGHT)
            
            # --- 1. Generar imágenes transparentes y bounds de los últimos 3 scans ---
            # Esto permite visualizar la animación de entrada en el frontend
            logging.info("Generando imágenes para los últimos 3 inputs...")
            last_3_inputs = full_paths[-3:]
            for input_nc_path in last_3_inputs:
                input_seq_id = os.path.splitext(os.path.basename(input_nc_path))[0]
                input_image_filename = f"INPUT_{input_seq_id}.png"
                input_image_path = os.path.join(IMAGE_OUTPUT_DIR, input_image_filename)
                
                # Solo generar si no existe (optimización)
                if not os.path.exists(input_image_path):
                    # Aumentamos skip_levels a 3 para enmascarar indices 0, 1 y 2 (clutter)
                    bounds, cells = generar_imagen_transparente_y_bounds(input_nc_path, input_image_path, skip_levels=3)
                    if bounds:
                        with open(f"{input_image_path}.json", 'w') as f:
                            json.dump({"bounds": bounds, "cells": cells}, f)
                else:
                    logging.info(f"Imagen de input ya existe: {input_image_filename}")

            # --- 2. Predecir ---
            input_tensor = load_and_preprocess_input_sequence(full_paths)
            prediction_tensor = predictor.predict(input_tensor)
            prediction_cleaned = postprocess_prediction(prediction_tensor)
            try:
                last_input_dt_utc = datetime.strptime(seq_id, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            except ValueError:
                last_input_dt_utc = datetime.now(timezone.utc)
            
            # --- 2.1 Detect/Validate Interval ---
            # Calculate interval from the last 2 files to be precise
            try:
                t1_str = os.path.splitext(os.path.basename(full_paths[-2]))[0]
                t2_str = os.path.splitext(os.path.basename(full_paths[-1]))[0]
                t1 = datetime.strptime(t1_str, '%Y%m%d%H%M%S')
                t2 = datetime.strptime(t2_str, '%Y%m%d%H%M%S')
                detected_interval = (t2 - t1).total_seconds() / 60.0
                if 2.0 <= detected_interval <= 15.0: # Sanity check
                    DATA_CONFIG['prediction_interval_minutes'] = detected_interval
                    logging.info(f"Intervalo detectado dinámicamente: {detected_interval:.2f} min")
                else:
                    logging.warning(f"Intervalo detectado ({detected_interval}) fuera de rango. Usando config: {DATA_CONFIG['prediction_interval_minutes']}")
            except Exception as e:
                logging.warning(f"No se pudo detectar intervalo dinámico: {e}. Usando config: {DATA_CONFIG['prediction_interval_minutes']}")

            # --- 3. Guardar predicciones en NetCDF ---
            output_subdir_name = last_input_dt_utc.strftime('%Y%m%d-%H%M%S')
            output_subdir_path = os.path.join(OUTPUT_DIR, output_subdir_name)
            os.makedirs(output_subdir_path, exist_ok=True)
            save_prediction_as_netcdf(output_subdir_path, prediction_cleaned, DATA_CONFIG, last_input_dt_utc)
            
            # Registrar en DB
            log_prediction(datetime.now(timezone.utc), seq_id, output_subdir_path, "SUCCESS")


            # --- 4. Convertir predicciones a MDV ---
            params_template_path = "/app/lrose_params/params.nc2mdv.final"
            convert_predictions_to_mdv(output_subdir_path, MDV_OUTPUT_DIR, params_template_path)

            # --- 5. Generar imágenes transparentes y bounds de las predicciones ---
            logging.info("Iniciando generación de imágenes de predicción...")
            prediction_nc_files = sorted(glob.glob(os.path.join(output_subdir_path, "*.nc")))
            for nc_file in prediction_nc_files:
                pred_filename_base = os.path.splitext(os.path.basename(nc_file))[0]
                # Incluimos el ID de la corrida (output_subdir_name) en el nombre de la imagen
                # Formato: PRED_<RUN_ID>_<FORECAST_TIME>.png
                pred_image_filename = f"PRED_{output_subdir_name}_{pred_filename_base}.png"
                pred_image_path = os.path.join(IMAGE_OUTPUT_DIR, pred_image_filename)
                # Aumentamos skip_levels a 3 para enmascarar indices 0, 1 y 2 (clutter)
                pred_bounds, pred_cells = generar_imagen_transparente_y_bounds(nc_file, pred_image_path, skip_levels=3)
                if pred_bounds:
                    with open(f"{pred_image_path}.json", 'w') as f:
                        json.dump({"bounds": pred_bounds, "cells": pred_cells}, f)

            # --- 6. Gestión del buffer (BATCH TRIGGER) ---
            # Eliminamos el archivo más antiguo para esperar 1 nuevo (Windows Stride = 1)
            # Esto permite ejecutar el modelo cada vez que llega UN archivo nuevo.
            files_to_remove = files_to_process[:1]
            for file_to_remove in files_to_remove:
                path_to_archive = os.path.join(INPUT_DIR, file_to_remove)
                logging.info(f"Ventana deslizante: archivando '{file_to_remove}' para esperar nuevos escaneos.")
                shutil.move(path_to_archive, os.path.join(ARCHIVE_DIR, file_to_remove))
            
            logging.info(f"Ciclo de predicción para la secuencia {seq_id} completado.")
            time.sleep(1)

        except Exception as e:
            update_status("ERROR - ver logs para detalles", -1, -1)
            logging.error(f"Ocurrió un error en el bucle principal: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL_SECONDS * 2)

if __name__ == "__main__":
    main()
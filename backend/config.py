import os
import torch
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Rutas del Pipeline ---
# Todas las rutas deben ser relativas a la raíz del contenedor (/app)
# Auto-detect model path
if os.getenv("MODEL_PATH"):
    MODEL_PATH = os.getenv("MODEL_PATH")
elif os.path.exists("/workspace/model/best_convlstm_model.pth"):
    MODEL_PATH = "/workspace/model/best_convlstm_model.pth"
else:
    MODEL_PATH = "/app/model/best_convlstm_model.pth"
INPUT_DIR = "/app/input_scans/"          # Buffer para archivos NC listos para predecir
OUTPUT_DIR = "/app/output_predictions/"   # Salida de predicciones en NC
ARCHIVE_DIR = "/app/archive_scans/"       # Archivo para los NC ya procesados
MDV_INBOX_DIR = "/app/mdv_inbox/"         # Bandeja de entrada para archivos MDV
MDV_ARCHIVE_DIR = "/app/mdv_archive/"     # Archivo para los MDV ya convertidos
MDV_OUTPUT_DIR = "/app/mdv_predictions/"  # Salida de predicciones en MDV
IMAGE_OUTPUT_DIR = "/app/output_images"
STATUS_FILE_PATH = "/app/status.json"     # Archivo de estado para la API
DB_PATH = "/app/data/radar_history.db"    # Base de datos SQLite

# --- Parámetros del Watcher ---
SECUENCE_LENGHT = 8
POLL_INTERVAL_SECONDS = 10

# --- Configuración del Dispositivo ---
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- Configuración del Modelo ---
MODEL_CONFIG = {
    'input_dim': 1, 'hidden_dims': [128, 128, 128], 'kernel_sizes': [(3, 3), (3, 3), (3, 3)],
    'num_layers': 3, 'pred_steps': 7, 'use_layer_norm': True,
    'img_height': 250, 'img_width': 250
}

# --- Configuración de Datos ---
DATA_CONFIG = {
    'min_dbz': -29.0, 'max_dbz': 65.0, 'variable_name': 'DBZ',
    'prediction_interval_minutes': 3.5,
    'physical_threshold_dbz': 30.0,
    'sensor_latitude': -34.64799880981445,
    'sensor_longitude': -68.01699829101562,
    'sensor_altitude_km': 0.55,
    'earth_radius_m': 6378137.0,

    # Parámetros para empaquetar la salida como byte, igual que el archivo de entrada
    'output_nc_scale_factor': 0.5,
    'output_nc_add_offset': 33.5,
    'output_nc_fill_value': -128, # _FillValue para el tipo byte
}

# --- Configuración de Inferencia ---
Z_BATCH_SIZE = 2

# --- Seguridad ---
# IMPORTANTE: En producción, SECRET_KEY debe estar en variables de entorno
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-this-in-prod")
if not os.getenv("SECRET_KEY"):
    print("⚠️  WARNING: Using insecure default SECRET_KEY. Set 'SECRET_KEY' env var in production.")

# CORS / Frontend Domain
# Remove trailing slash to match Browser Origin header format
FRONTEND_URL = os.getenv("FRONTEND_URL", "*").rstrip("/")

# --- VAPID Keys for Push Notifications ---
# Generated with `vapid --gen`
# in production, set these via environment variables or file mounts
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
if VAPID_PRIVATE_KEY:
    VAPID_PRIVATE_KEY = VAPID_PRIVATE_KEY.replace("\\n", "\n")

VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")
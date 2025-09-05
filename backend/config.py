# backend/config.py
import torch

# --- Rutas del Pipeline ---
# Todas las rutas deben ser relativas a la raíz del contenedor (/app)
MODEL_PATH = "/app/model/best_convlstm_model.pth"
INPUT_DIR = "/app/input_scans/"          # Buffer para archivos NC listos para predecir
OUTPUT_DIR = "/app/output_predictions/"   # Salida de predicciones en NC
ARCHIVE_DIR = "/app/archive_scans/"       # Archivo para los NC ya procesados
MDV_INBOX_DIR = "/app/mdv_inbox/"         # Bandeja de entrada para archivos MDV
MDV_ARCHIVE_DIR = "/app/mdv_archive/"     # Archivo para los MDV ya convertidos
MDV_OUTPUT_DIR = "/app/mdv_predictions/"  # Salida de predicciones en MDV
STATUS_FILE_PATH = "/app/status.json"     # Archivo de estado para la API

# --- Parámetros del Watcher ---
SECUENCE_LENGHT = 12
POLL_INTERVAL_SECONDS = 10

# --- Configuración del Dispositivo ---
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- Configuración del Modelo ---
MODEL_CONFIG = {
    'input_dim': 1, 'hidden_dims': [128, 128, 128], 'kernel_sizes': [(3, 3), (3, 3), (3, 3)],
    'num_layers': 3, 'pred_steps': 5, 'use_layer_norm': True,
    'img_height': 500, 'img_width': 500
}

# --- Configuración de Datos ---
DATA_CONFIG = {
    'min_dbz': -29.0, 'max_dbz': 65.0, 'variable_name': 'DBZ',
    'prediction_interval_minutes': 3,
    'physical_threshold_dbz': 30.0,
    'sensor_latitude': -34.64799880981445,
    'sensor_longitude': -68.01699829101562,
    'earth_radius_m': 6378137.0,

    # Parámetros para empaquetar la salida como byte, igual que el archivo de entrada
    'output_nc_scale_factor': 0.5,
    'output_nc_add_offset': 33.5,
    'output_nc_fill_value': -128, # _FillValue para el tipo byte
}

# --- Parámetros de Inferencia ---
Z_BATCH_SIZE = 2
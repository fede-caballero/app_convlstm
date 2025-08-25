# backend/config.py
import torch

# --- Rutas del Pipeline ---
# Estas rutas son DENTRO del contenedor de Docker en vast.ai
MODEL_PATH = "/home/model/best_convlstm_model.pth"
INPUT_DIR = "/home/app/input_scans/"
OUTPUT_DIR = "/home/app/output_predictions/"
ARCHIVE_DIR = "/home/app/archive_scans/"

# --- Parámetros del Watcher ---
SECUENCE_LENGHT = 12  # Número de archivos para disparar la predicción
POLL_INTERVAL_SECONDS = 10 # Tiempo de espera entre cada revisión de la carpeta

# --- Configuración del Dispositivo ---
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- Configuración del Modelo (de tu batch_inference_new.py) ---
MODEL_CONFIG = {
    'input_dim': 1, 'hidden_dims': [128, 128, 128], 'kernel_sizes': [(3, 3), (3, 3), (3, 3)],
    'num_layers': 3, 'pred_steps': 5, 'use_layer_norm': True,
    'img_height': 500, 'img_width': 500
}

# --- Configuración de Datos (de tu batch_inference_new.py) ---
DATA_CONFIG = {
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

# --- Parámetros de Inferencia ---
Z_BATCH_SIZE = 2 # Lotes de niveles de altura para no saturar la VRAM
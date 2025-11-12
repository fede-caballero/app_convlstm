# ==============================================================================
# CONFIGURACIÓN DEL SCRIPT DE ENTRENAMIENTO
# ==============================================================================

CONFIG = {
    # --- Rutas dentro del contenedor Docker ---
    'dataset_root_dir': "/app/datasets",
    'model_save_dir': "/app/model_output",
    'predictions_output_dir': "/app/predictions_output",

    # --- Parámetros del Dataset y Descarga ---
    'dataset_gdown_id': '12-Ry9JtHpkBsjXWiWFqR-bPFlBNYCdjw',
    'dataset_archive_name': 'sample.tar.gz',
    'dataset_unpacked_name': 'sample',

    # --- Parámetros de Pre-procesamiento y Secuencia ---
    'downsample_size': (250, 250),
    'original_size': (500, 500),
    'z_levels': 18,
    'seq_len': 8,
    'pred_len': 7,

    # --- Parámetros de División del Dataset ---
    'train_val_split_ratio': 0.8,

    # --- Parámetros de Normalización y Físicos ---
    'min_dbz_norm': -29.0,
    'max_dbz_norm': 65.0,
    
    # --- Parámetros del Modelo (PredRNN++ 3D) ---
    'model_input_dim': 1,
    'model_hidden_dims': [64, 64, 64],
    'model_kernel_sizes': [(3, 3, 3), (3, 3, 3), (3, 3, 3)],
    'model_num_layers': 3,
    'model_use_layer_norm': True,

    # --- Parámetros de Entrenamiento Generales ---
    'batch_size': 16,
    'use_amp': True,
    'clip_grad_norm': 1.0,
    'accumulation_steps': 2,
    'log_interval': 1,
    'checkpoint_interval': 5,
    'seed': 42,

    # --- Parámetros de Georreferenciación y Salida ---
    'sensor_longitude': -68.01699829101562,
    'sensor_latitude': -34.64799880981445,
    'earth_radius_m': 6378137.0,
    'prediction_interval_minutes': 3
}
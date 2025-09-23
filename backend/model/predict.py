import torch
import logging

from config import DEVICE, MODEL_CONFIG, Z_BATCH_SIZE

from model.architecture import ConvLSTM3D_Enhanced

class ModelPredictor:
    # Clase para la carga del modelo y ejecución de predicciones
    def __init__(self, model_path: str):
        # Al iniciar, carga el modelo y lo prepara

        # Args: model_path (str): Ruta al archivo .pth del modelo entrenado

        self.model = self._load_model(model_path)
    
    def _load_model(self, model_path: str):
        # Carga el modelo desde el archivo .pth

        logging.info(f"Cargando modelo desde {model_path}...")
        try:
            # 1. Construir la arquitectura del modelo usando la configuración
            model = ConvLSTM3D_Enhanced(**MODEL_CONFIG)

            # 2. Cargar los pesos entrenados
            # weights_only=True
            checkpoint = torch.load(model_path, map_location=DEVICE, weights_only=False)
            model.load_state_dict(checkpoint['model_state_dict'])

            # 3. Mover el modelo al dispositivo adecuado
            model.to(DEVICE)

            # 4. Poner el modelo en modo evaluación 
            model.eval()

            logging.info("Modelo cargado y listo para predicciones.")
            return model
        except FileNotFoundError:
            logging.error(f"Archivo de modelo no encontrado en {model_path}. Asegúrate de que la ruta es correcta.")
            raise
        except Exception as e:
            logging.error(f"Error al cargar el modelo: {e}", exc_info=True)
            raise
    
    # En backend/model/predict.py

    def predict(self, input_volume: torch.Tensor) -> torch.Tensor:
        """
        Realiza una predicción en un volumen de datos de entrada.

        Args:
            input_volume (torch.Tensor): El tensor de entrada pre-procesado.
                                        Shape: (Z, T, H, W, C).

        Returns:
            torch.Tensor: El tensor de predicción.
        """
        x_to_model_full = input_volume.permute(0, 1, 4, 2, 3).to(DEVICE)
        num_z_levels = x_to_model_full.shape[0]
        
        # --- CORRECCIÓN CLAVE AQUÍ ---
        # La lista se llamará 'all_predictions_chunks' de principio a fin.
        all_predictions_chunks = []

        logging.info(f"Iniciando predicción para {num_z_levels} niveles de altura...")

        for z_start in range(0, num_z_levels, Z_BATCH_SIZE):
            z_end = min(z_start + Z_BATCH_SIZE, num_z_levels)
            x_chunk = x_to_model_full[z_start:z_end, ...]

            with torch.no_grad(), torch.amp.autocast(device_type="cuda"):
                prediction_chunk = self.model(x_chunk)

            # Usamos el nombre correcto de la lista
            all_predictions_chunks.append(prediction_chunk.cpu())

        # Concatenamos los resultados
        prediction_norm = torch.cat(all_predictions_chunks, dim=0)
        logging.info(f"Predicción completada. Input shape: {x_to_model_full.shape}, Output shape: {prediction_norm.shape}")

        # Liberamos memoria
        del x_to_model_full, all_predictions_chunks, x_chunk
        torch.cuda.empty_cache()

        return prediction_norm
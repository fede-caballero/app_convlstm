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

    def predict(self, input_tensor: torch.Tensor) -> torch.Tensor:
        """
        Realiza una predicción.
        Args:
            input_tensor (torch.Tensor): Tensor de entrada (B, T, C, H, W).
        Returns:
            torch.Tensor: Tensor de predicción (B, T, C, H, W).
        """
        self.model.eval()
        with torch.no_grad():
            x = input_tensor.to(DEVICE)
            # El modelo espera (B, T, C, H, W)
            # Ya no hacemos slicing en Z porque el worker entrega el tensor listo (Max Composite).
            prediction = self.model(x)
            
        return prediction.cpu()
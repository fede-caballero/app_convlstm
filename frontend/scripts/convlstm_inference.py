import torch
import numpy as np
import xarray as xr
import argparse
from pathlib import Path
import logging
from typing import List
import sys

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConvLSTMInference:
    def __init__(self, model_path: str, device: str = "cuda"):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        logger.info(f"Usando device: {self.device}")
        
        # Cargar modelo (ajustar según tu implementación)
        self.model = self.load_model(model_path)
        self.model.eval()
        
    def load_model(self, model_path: str):
        """Carga el modelo convLSTM entrenado"""
        try:
            # Ajustar según tu implementación específica
            model = torch.load(model_path, map_location=self.device)
            logger.info(f"Modelo cargado desde: {model_path}")
            return model
        except Exception as e:
            logger.error(f"Error cargando modelo: {e}")
            sys.exit(1)
    
    def load_netcdf_files(self, file_paths: List[str]) -> np.ndarray:
        """Carga y preprocesa archivos NetCDF"""
        try:
            data_arrays = []
            
            for file_path in file_paths:
                # Cargar archivo NetCDF
                ds = xr.open_dataset(file_path)
                
                # Extraer datos de radar (ajustar según tu estructura de datos)
                # Asumiendo que tienes una variable llamada 'reflectivity' o similar
                radar_data = ds['reflectivity'].values  # Ajustar nombre de variable
                
                # Normalización y preprocesamiento
                radar_data = self.preprocess_data(radar_data)
                data_arrays.append(radar_data)
                
                ds.close()
            
            # Convertir a tensor de PyTorch
            # Shape esperado: (batch_size, sequence_length, channels, height, width)
            input_tensor = np.stack(data_arrays, axis=0)  # (12, H, W)
            input_tensor = np.expand_dims(input_tensor, axis=0)  # (1, 12, H, W)
            input_tensor = np.expand_dims(input_tensor, axis=2)  # (1, 12, 1, H, W)
            
            logger.info(f"Datos cargados. Shape: {input_tensor.shape}")
            return input_tensor
            
        except Exception as e:
            logger.error(f"Error cargando archivos NetCDF: {e}")
            return None
    
    def preprocess_data(self, data: np.ndarray) -> np.ndarray:
        """Preprocesa los datos de radar"""
        # Normalización (ajustar según tus datos)
        # Ejemplo: normalizar reflectividad de dBZ
        data = np.clip(data, -10, 70)  # Clip valores extremos
        data = (data + 10) / 80  # Normalizar a [0, 1]
        
        # Manejar valores NaN
        data = np.nan_to_num(data, nan=0.0)
        
        return data
    
    def postprocess_predictions(self, predictions: np.ndarray) -> np.ndarray:
        """Postprocesa las predicciones del modelo"""
        # Desnormalizar
        predictions = predictions * 80 - 10  # Revertir normalización
        predictions = np.clip(predictions, -10, 70)  # Clip a rango válido
        
        return predictions
    
    def predict(self, input_data: np.ndarray) -> np.ndarray:
        """Ejecuta predicción con el modelo convLSTM"""
        try:
            # Convertir a tensor de PyTorch
            input_tensor = torch.FloatTensor(input_data).to(self.device)
            
            logger.info("Ejecutando predicción...")
            with torch.no_grad():
                predictions = self.model(input_tensor)
            
            # Convertir de vuelta a numpy
            predictions = predictions.cpu().numpy()
            
            # Postprocesar
            predictions = self.postprocess_predictions(predictions)
            
            logger.info(f"Predicción completada. Shape: {predictions.shape}")
            return predictions
            
        except Exception as e:
            logger.error(f"Error en predicción: {e}")
            return None
    
    def save_predictions(self, predictions: np.ndarray, output_dir: str, output_prefix: str):
        """Guarda las predicciones como archivos NetCDF"""
        try:
            output_dir = Path(output_dir)
            
            # Asumiendo que predictions tiene shape (1, 5, 1, H, W)
            for t in range(predictions.shape[1]):  # 5 time steps
                pred_data = predictions[0, t, 0, :, :]  # (H, W)
                
                # Crear dataset NetCDF
                ds = xr.Dataset({
                    'reflectivity': (['y', 'x'], pred_data)
                })
                
                # Agregar metadatos (ajustar según tus necesidades)
                ds.attrs['description'] = f'ConvLSTM prediction t+{t+1}'
                ds.attrs['units'] = 'dBZ'
                
                # Guardar archivo
                output_file = output_dir / f"{output_prefix}_t{t+1}.nc"
                ds.to_netcdf(output_file)
                logger.info(f"Predicción guardada: {output_file}")
                
        except Exception as e:
            logger.error(f"Error guardando predicciones: {e}")

def main():
    parser = argparse.ArgumentParser(description='ConvLSTM Inference')
    parser.add_argument('--input_list', required=True, help='Archivo con lista de NetCDF de entrada')
    parser.add_argument('--output_dir', required=True, help='Directorio de salida')
    parser.add_argument('--output_prefix', required=True, help='Prefijo para archivos de salida')
    parser.add_argument('--model_path', default='/models/convlstm_model.pth', help='Ruta al modelo')
    
    args = parser.parse_args()
    
    # Leer lista de archivos de entrada
    with open(args.input_list, 'r') as f:
        input_files = [line.strip() for line in f.readlines()]
    
    logger.info(f"Procesando {len(input_files)} archivos de entrada")
    
    # Crear inferencia
    inference = ConvLSTMInference(args.model_path)
    
    # Cargar datos
    input_data = inference.load_netcdf_files(input_files)
    if input_data is None:
        logger.error("No se pudieron cargar los datos de entrada")
        sys.exit(1)
    
    # Ejecutar predicción
    predictions = inference.predict(input_data)
    if predictions is None:
        logger.error("No se pudo ejecutar la predicción")
        sys.exit(1)
    
    # Guardar resultados
    inference.save_predictions(predictions, args.output_dir, args.output_prefix)
    logger.info("Inferencia completada exitosamente")

if __name__ == "__main__":
    main()

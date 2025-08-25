import os
import time
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import subprocess
import logging
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
import json

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RadarScan:
    mdv_path: str
    netcdf_path: str
    timestamp: datetime
    status: str = "processing"

class RadarProcessor:
    def __init__(self, 
                 mdv_input_dir: str,
                 netcdf_output_dir: str,
                 predictions_dir: str,
                 mdv_predictions_dir: str,
                 buffer_size: int = 12):
        
        self.mdv_input_dir = Path(mdv_input_dir)
        self.netcdf_output_dir = Path(netcdf_output_dir)
        self.predictions_dir = Path(predictions_dir)
        self.mdv_predictions_dir = Path(mdv_predictions_dir)
        self.buffer_size = buffer_size
        
        # Buffer deslizante de escaneos
        self.scan_buffer: List[RadarScan] = []
        
        # Crear directorios si no existen
        for dir_path in [self.netcdf_output_dir, self.predictions_dir, self.mdv_predictions_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"RadarProcessor inicializado. Buffer size: {buffer_size}")
    
    def convert_mdv_to_netcdf(self, mdv_path: str) -> Optional[str]:
        """Convierte archivo MDV a NetCDF usando Mdv2NetCDF"""
        try:
            mdv_file = Path(mdv_path)
            netcdf_file = self.netcdf_output_dir / f"{mdv_file.stem}.nc"
            
            # Comando Mdv2NetCDF (ajustar según tu instalación)
            cmd = [
                "Mdv2NetCDF",
                "-f", str(mdv_path),
                "-o", str(netcdf_file)
            ]
            
            logger.info(f"Convirtiendo {mdv_path} a NetCDF...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"Conversión exitosa: {netcdf_file}")
                return str(netcdf_file)
            else:
                logger.error(f"Error en conversión MDV->NetCDF: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout en conversión de {mdv_path}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado en conversión: {e}")
            return None
    
    def convert_netcdf_to_mdv(self, netcdf_path: str, output_mdv_path: str) -> bool:
        """Convierte NetCDF a MDV usando NcGeneric2Mdv"""
        try:
            # Comando NcGeneric2Mdv (ajustar según tu instalación)
            cmd = [
                "NcGeneric2Mdv",
                "-f", netcdf_path,
                "-o", output_mdv_path
            ]
            
            logger.info(f"Convirtiendo {netcdf_path} a MDV...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"Conversión exitosa: {output_mdv_path}")
                return True
            else:
                logger.error(f"Error en conversión NetCDF->MDV: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout en conversión de {netcdf_path}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado en conversión: {e}")
            return False
    
    async def run_convlstm_model(self, input_files: List[str]) -> List[str]:
        """Ejecuta el modelo convLSTM con los 12 archivos NetCDF"""
        try:
            logger.info(f"Ejecutando modelo convLSTM con {len(input_files)} archivos...")
            
            # Crear archivo temporal con la lista de archivos de entrada
            input_list_file = self.predictions_dir / "input_files.txt"
            with open(input_list_file, 'w') as f:
                for file_path in input_files:
                    f.write(f"{file_path}\n")
            
            # Generar nombres para los 5 archivos de predicción
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prediction_files = []
            for i in range(5):
                pred_file = self.predictions_dir / f"prediction_{timestamp}_t{i+1}.nc"
                prediction_files.append(str(pred_file))
            
            # Comando para ejecutar tu modelo convLSTM
            # Ajustar según tu implementación específica
            cmd = [
                "python", "/path/to/your/convlstm_inference.py",
                "--input_list", str(input_list_file),
                "--output_dir", str(self.predictions_dir),
                "--output_prefix", f"prediction_{timestamp}"
            ]
            
            # Ejecutar modelo (esto puede tomar varios minutos)
            logger.info("Iniciando inferencia del modelo...")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Modelo ejecutado exitosamente")
                # Verificar que los archivos de predicción existan
                existing_predictions = []
                for pred_file in prediction_files:
                    if Path(pred_file).exists():
                        existing_predictions.append(pred_file)
                
                logger.info(f"Generadas {len(existing_predictions)} predicciones")
                return existing_predictions
            else:
                logger.error(f"Error en ejecución del modelo: {stderr.decode()}")
                return []
                
        except Exception as e:
            logger.error(f"Error inesperado en ejecución del modelo: {e}")
            return []
    
    async def process_predictions_to_mdv(self, prediction_files: List[str]) -> List[str]:
        """Convierte las predicciones NetCDF a MDV"""
        mdv_predictions = []
        
        for i, netcdf_pred in enumerate(prediction_files):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mdv_pred = self.mdv_predictions_dir / f"prediction_{timestamp}_t{i+1}.mdv"
            
            if self.convert_netcdf_to_mdv(netcdf_pred, str(mdv_pred)):
                mdv_predictions.append(str(mdv_pred))
        
        logger.info(f"Convertidas {len(mdv_predictions)} predicciones a MDV")
        return mdv_predictions
    
    async def add_scan_to_buffer(self, mdv_path: str):
        """Agrega un nuevo escaneo al buffer y procesa si es necesario"""
        logger.info(f"Procesando nuevo escaneo: {mdv_path}")
        
        # Convertir MDV a NetCDF
        netcdf_path = self.convert_mdv_to_netcdf(mdv_path)
        if not netcdf_path:
            logger.error(f"No se pudo convertir {mdv_path} a NetCDF")
            return
        
        # Crear objeto RadarScan
        scan = RadarScan(
            mdv_path=mdv_path,
            netcdf_path=netcdf_path,
            timestamp=datetime.now(),
            status="ready"
        )
        
        # Agregar al buffer
        self.scan_buffer.append(scan)
        
        # Mantener solo los últimos 12 escaneos
        if len(self.scan_buffer) > self.buffer_size:
            removed_scan = self.scan_buffer.pop(0)
            logger.info(f"Removido del buffer: {removed_scan.mdv_path}")
        
        logger.info(f"Buffer actual: {len(self.scan_buffer)}/{self.buffer_size}")
        
        # Si tenemos 12 escaneos, ejecutar predicción
        if len(self.scan_buffer) == self.buffer_size:
            await self.generate_prediction()
    
    async def generate_prediction(self):
        """Genera predicción usando los 12 escaneos del buffer"""
        logger.info("Iniciando generación de predicción...")
        
        # Obtener archivos NetCDF del buffer
        input_files = [scan.netcdf_path for scan in self.scan_buffer]
        
        # Ejecutar modelo convLSTM
        prediction_files = await self.run_convlstm_model(input_files)
        
        if prediction_files:
            # Convertir predicciones a MDV
            mdv_predictions = await self.process_predictions_to_mdv(prediction_files)
            
            # Notificar resultado (aquí podrías enviar via WebSocket al frontend)
            result = {
                "timestamp": datetime.now().isoformat(),
                "input_scans": len(input_files),
                "predictions_netcdf": prediction_files,
                "predictions_mdv": mdv_predictions,
                "status": "completed"
            }
            
            logger.info(f"Predicción completada: {len(mdv_predictions)} archivos MDV generados")
            
            # Guardar resultado en archivo JSON para el frontend
            result_file = self.predictions_dir / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
        
        else:
            logger.error("No se pudieron generar predicciones")

class MDVFileHandler(FileSystemEventHandler):
    def __init__(self, processor: RadarProcessor):
        self.processor = processor
        super().__init__()
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.mdv'):
            # Usar asyncio para manejar el procesamiento asíncrono
            asyncio.create_task(self.processor.add_scan_to_buffer(event.src_path))

async def main():
    # Configuración de directorios
    config = {
        "mdv_input_dir": "/data/radar/mdv",
        "netcdf_output_dir": "/data/radar/netcdf",
        "predictions_dir": "/data/radar/predictions",
        "mdv_predictions_dir": "/data/radar/predictions_mdv",
        "buffer_size": 12
    }
    
    # Crear procesador
    processor = RadarProcessor(**config)
    
    # Configurar file watcher
    event_handler = MDVFileHandler(processor)
    observer = Observer()
    observer.schedule(event_handler, config["mdv_input_dir"], recursive=False)
    
    # Iniciar monitoreo
    observer.start()
    logger.info(f"Iniciando monitoreo de archivos MDV en: {config['mdv_input_dir']}")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Deteniendo monitoreo...")
    
    observer.join()

if __name__ == "__main__":
    asyncio.run(main())

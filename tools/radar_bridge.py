import sys
import time
import logging
import argparse
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class MDVUploadHandler(FileSystemEventHandler):
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.upload_endpoint = f"{api_url.rstrip('/')}/api/upload_mdv"
        logger.info(f"Target API Endpoint: {self.upload_endpoint}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.mdv'):
            self.upload_file(event.src_path)

    def upload_file(self, file_path):
        logger.info(f"Nuevo archivo detectado: {file_path}")
        
        # Pequeña pausa para asegurar que el archivo terminó de escribirse
        time.sleep(1) 
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f)}
                # Enviar archivo a la API
                response = requests.post(self.upload_endpoint, files=files, timeout=30)
                
            if response.status_code == 201:
                logger.info(f"✅ Subido exitosamente: {file_path}")
            else:
                logger.error(f"❌ Error al subir {file_path}. Code: {response.status_code}, Msg: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Excepción al subir {file_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Radar Bridge: Watch folder & Upload to API")
    parser.add_argument("--folder", required=True, help="Local folder to watch for .mdv files")
    parser.add_argument("--api", required=True, help="URL of the Vast.ai backend (e.g., http://1.2.3.4:8000)")
    
    args = parser.parse_args()
    
    watch_folder = Path(args.folder)
    
    if not watch_folder.exists():
        logger.error(f"El directorio {watch_folder} no existe.")
        sys.exit(1)
        
    logger.info(f"🛰️ Iniciando Radar Bridge...")
    logger.info(f"📂 Monitoreando: {watch_folder}")
    logger.info(f"📡 Destino: {args.api}")
    
    event_handler = MDVUploadHandler(api_url=args.api)
    observer = Observer()
    observer.schedule(event_handler, str(watch_folder), recursive=False)
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Deteniendo Radar Bridge...")
        
    observer.join()

if __name__ == "__main__":
    main()

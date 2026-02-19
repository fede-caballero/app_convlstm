import os
import time
import subprocess
import logging
import argparse
from datetime import datetime, timezone
import glob

# --- Configuración ---
# Ajustar según la estructura del contenedor Docker
MDV_INBOX_DIR = "/app/mdv_inbox"
MDV_ARCHIVE_DIR = "/app/mdv_archive" # Files processed by worker are moved here
INPUT_DIR = "/app/input_scans"       # Files converted to NC end up here

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DriveWatcher")

def get_remote_path_for_today(base_remote_path: str):
    # Asumimos estructura plana por día: YYYYMMDD (Común en LROSE/TITAN)
    # Ejemplo: .../cart_no_clutter/20260125
    now = datetime.now(timezone.utc)
    return f"{base_remote_path}/{now.strftime('%Y%m%d')}"

def list_remote_files(remote_path: str):
    """Retorna una lista de nombres de archivos en el path remoto usando rclone."""
    try:
        # rclone lsf devuelve solo nombres de archivos (uno por linea)
        cmd = ["rclone", "lsf", remote_path, "--files-only"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        files = result.stdout.strip().split('\n')
        return [f for f in files if f.endswith('.mdv')]
    except subprocess.CalledProcessError as e:
        logger.warning(f"No se pudo listar archivos en {remote_path}: {e.stderr}")
        return []


# In-memory "processed" cache (for files skipped or downloaded in this session)
# This prevents re-evaluating old files if they are not in local folders (e.g. catch-up skipped)
metrics = {
    "downloaded": 0,
    "skipped": 0,
    "errors": 0
}
files_seen_this_session = set()

def is_processed(filename: str):
    """Verifica si el archivo ya existe localmente (en inbox, archivo o convertido) o fue saltado."""
    # 0. Check Session Cache
    if filename in files_seen_this_session:
        return True

    # 1. Check Inbox
    if os.path.exists(os.path.join(MDV_INBOX_DIR, filename)):
        return True
    
    # 2. Check Archive (Processed and moved)
    if os.path.exists(os.path.join(MDV_ARCHIVE_DIR, filename)):
        return True
    
    return False

def download_file(remote_path: str, filename: str):
    """Descarga un archivo específico a la bandeja de entrada."""
    remote_file = f"{remote_path}/{filename}"
    local_dest = MDV_INBOX_DIR
    
    logger.info(f"📥 Descargando nuevo archivo: {filename}")
    try:
        cmd = ["rclone", "copy", remote_file, local_dest]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"✅ Descarga completada: {filename}")
        files_seen_this_session.add(filename) # Mark as seen
        metrics["downloaded"] += 1
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error descargando {filename}: {e.stderr}")
        metrics["errors"] += 1
        return False

def main():
    parser = argparse.ArgumentParser(description="Google Drive Radar Watcher")
    parser.add_argument("--remote-base", required=True, help="Rclone remote base path (e.g. 'gdrive:Campaña/2025-2026')")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    
    args = parser.parse_args()
    
    logger.info("📡 Iniciando Drive Watcher...")
    
    # Asegurar directorios (aunque el worker debería crearlos)
    os.makedirs(MDV_INBOX_DIR, exist_ok=True)
    
    while True:
        try:
            # 1. Determinar carpeta del día
            current_remote_path = get_remote_path_for_today(args.remote_base)
            
            logger.debug(f"🔍 Consultando: {current_remote_path}")
            
            # 2. Listar archivos remotos
            remote_files = list_remote_files(current_remote_path)
            
            if not remote_files:
                logger.debug("No se encontraron archivos remotos (o error de conexión).")
            
            # 3. Filtrar y descargar nuevos
            remote_files.sort()

            # IDENTIFY NEW FILES (Using updated is_processed with cache)
            new_files = [f for f in remote_files if not is_processed(f)]
            
            # --- LOGIC UPDATE: Catch-up Strategy ---
            MAX_CATCHUP = 8 # Sufficient for 1 sequence
            
            files_to_download = []
            
            if len(new_files) > MAX_CATCHUP:
                logger.warning(f"⚠️ Demasiados archivos pendientes ({len(new_files)}). Saltando a los últimos {MAX_CATCHUP} para estar en vivo.")
                
                # Split: Skipped vs Downloaded
                files_to_skip = new_files[:-MAX_CATCHUP]
                files_to_download = new_files[-MAX_CATCHUP:]
                
                # Mark skipped files as "seen" to prevent re-processing next loop
                for f in files_to_skip:
                    files_seen_this_session.add(f)
                metrics["skipped"] += len(files_to_skip)
                
                logger.info(f"⏭️ Saltados {len(files_to_skip)} archivos antiguos (ej: {files_to_skip[0]} ... {files_to_skip[-1]})")
            else:
                files_to_download = new_files

            for f in files_to_download:
                download_file(current_remote_path, f)
            
            if not files_to_download and new_files:
                 logger.info("No new files to download (all pending were skipped by catch-up logic).")
            elif not new_files:
                 logger.debug("Todo al día.")
            
        except Exception as e:
            logger.error(f"Error en bucle principal: {e}")
            
        time.sleep(args.interval)

if __name__ == "__main__":
    main()

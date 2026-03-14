#!/bin/bash

# ==============================================================================
# Script para mover PNGs a Google Drive y eliminar archivos NC viejos (ahorrar espacio)
# ==============================================================================

# Directorio base de la aplicación (ajustar si es necesario en el VPS)
APP_DIR="/root/app_convlstm"

# Nombre del remoto configurado en rclone y la carpeta destino en Google Drive
# Deberá ser el mismo remoto que usas para MDV, por ejemplo: drive_dacc:Respaldo_Tesis
DRIVE_REMOTE="PON_EL_NOMBRE_AQUI:Respaldo_Tesis_PNG" 

echo "Iniciando mantenimiento de disco: $(date)"

# 1. MOVER IMÁGENES PNG AL DRIVE (y borrarlas del VPS)
# Mueve los PNG mayores a 1 día (--min-age 1d) a Drive. 
# Dejamos 1 día para que el frontend web todavía pueda mostrar algo reciente.
echo "Subiendo PNGs a Google Drive..."
rclone move $APP_DIR/output_images/ $DRIVE_REMOTE/ --include "*.png" --min-age 1d -v

# 2. ELIMINAR ARCHIVOS NETCDF VIEJOS DE FORMA PERMANENTE (No se suben a Drive porque son muy pesados e inservibles sin procesar)
# Borrar todos los .nc mayores a 2 días
echo "Purgando archivos .nc mayores a 2 días para liberar espacio..."
find $APP_DIR/input_scans/ -type f -name "*.nc" -mtime +2 -delete
find $APP_DIR/archive_scans/ -type f -name "*.nc" -mtime +2 -delete
find $APP_DIR/output_predictions/ -type f -name "*.nc" -mtime +2 -delete
find $APP_DIR/mdv_archive/ -type f -name "*.mdv" -mtime +2 -delete
find $APP_DIR/mdv_predictions/ -type f -name "*.mdv" -mtime +2 -delete

# También borramos cualquier carpeta de log o salida que haya quedado vacía
find $APP_DIR/output_predictions/ -type d -empty -delete

echo "Mantenimiento completado: $(date)"

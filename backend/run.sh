#!/bin/bash

# Script de inicio mejorado que guarda los logs en un archivo.

export PYTHONUNBUFFERED=1

# Crear un directorio para los logs si no existe
mkdir -p /app/logs
LOG_FILE="/app/logs/session_$(date +%Y%m%d_%H%M%S).log"

echo "============================================================"
echo "Iniciando Backend..."
echo "Los logs de esta sesión se guardarán en: $LOG_FILE"
echo "============================================================"

# Ejecuta ambos procesos. La salida de ambos (stdout y stderr)
# se redirige a 'tee', que la muestra en pantalla y la guarda en el archivo.
{
    echo "Iniciando Pipeline Worker en segundo plano..."
    python3 /app/pipeline_worker.py &

    echo "Iniciando API Server en el puerto 8080..."
    python3 /app/api.py

} 2>&1 | tee -a "$LOG_FILE"
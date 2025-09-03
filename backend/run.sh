#!/bin/bash

# Script de inicio para el contenedor Docker

# --- Variables de entorno ---
export PYTHONUNBUFFERED=1  # Para que la salida de Python no se almacene en búfer

# Inicia el worker del pipeline en segundo plano
echo "Iniciando Pipeline Worker en segundo plano..."
python3 /app/pipeline_worker.py &

# Inicia el servidor de la API de Flask en primer plano
# Este proceso se quedará corriendo y mantendrá el contenedor activo
echo "Iniciando API Server en el puerto 8080..."
python3 /app/api.py
#!/bin/bash
export PYTHONUNBUFFERED=1
echo "Iniciando Pipeline Worker en segundo plano..."
python3 /app/pipeline_worker.py &
echo "Iniciando API Server en el puerto 8080..."
python3 /app/api.py
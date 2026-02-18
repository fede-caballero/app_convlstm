#!/bin/bash

# Script para reiniciar los servicios del backend (Watcher y Worker)
# Uso: ./tools/restart_services.sh

echo "========================================"
echo "Reiniciando servicios de HaliCast..."
echo "========================================"

# 1. Detener procesos actuales
echo "Deteniendo procesos antiguos..."
pkill -f drive_watcher.py || true
pkill -f pipeline_worker.py || true

# 2. Iniciar Drive Watcher (Intervalo 10s)
echo "Iniciando Drive Watcher (10s)..."
# Asegúrate de que la ruta remota sea la correcta. Por defecto: mydrive:cart_no_clutter
REMOTE_BASE="mydrive:cart_no_clutter"
nohup python3 /app/tools/drive_watcher.py --remote-base "$REMOTE_BASE" --interval 10 > /app/logs/watcher.log 2>&1 &
echo "Watcher iniciado (PID $!)."

# 3. Iniciar Pipeline Worker
echo "Iniciando Pipeline Worker..."
nohup python3 /app/pipeline_worker.py > /app/logs/worker.log 2>&1 &
echo "Worker iniciado (PID $!)."

echo "========================================"
echo "¡Servicios reiniciados correctamente!"
echo "Verifica los logs con: tail -f /app/logs/*.log"
echo "========================================"

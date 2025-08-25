#!/bin/bash

# Script de configuración del entorno para el sistema de predicción de radar

echo "Configurando entorno para sistema de predicción de radar..."

# Crear directorios necesarios
mkdir -p /data/radar/mdv
mkdir -p /data/radar/netcdf
mkdir -p /data/radar/predictions
mkdir -p /data/radar/predictions_mdv
mkdir -p /models
mkdir -p /logs

# Instalar dependencias Python
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install fastapi uvicorn websockets
pip install watchdog
pip install xarray netcdf4
pip install numpy pandas
pip install pathlib logging

echo "Instalación de dependencias completada."

# Configurar variables de entorno
export CUDA_VISIBLE_DEVICES=0
export PYTHONPATH="${PYTHONPATH}:/app"

# Configurar permisos
chmod +x /app/scripts/*.py
chmod +x /app/scripts/*.sh

echo "Configuración completada."
echo "Directorios creados:"
echo "  - /data/radar/mdv (archivos MDV de entrada)"
echo "  - /data/radar/netcdf (archivos NetCDF convertidos)"
echo "  - /data/radar/predictions (predicciones NetCDF)"
echo "  - /data/radar/predictions_mdv (predicciones MDV finales)"
echo ""
echo "Para iniciar el sistema:"
echo "  1. python scripts/file_watcher.py (monitoreo automático)"
echo "  2. python scripts/api_server.py (API y WebSocket)"
echo ""
echo "Asegúrate de:"
echo "  - Configurar las rutas de Mdv2NetCDF y NcGeneric2Mdv"
echo "  - Colocar tu modelo convLSTM en /models/"
echo "  - Ajustar las rutas en convlstm_inference.py"

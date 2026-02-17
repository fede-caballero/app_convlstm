#!/bin/bash

# =================================================================
# Script de Inicio Robusto para el Backend
# - Inicia ambos servicios (worker y API).
# - Guarda los logs en un archivo Y LOS MUESTRA EN CONSOLA.
# - Atrapa la señal de Ctrl+C para una detención limpia.
# =================================================================

export PYTHONUNBUFFERED=1

# --- Configuración de Logs ---
LOG_DIR="/app/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/session_$(date +%Y%m%d_%H%M%S).log"

# Tocar el archivo de log para que tail no falle si no se escribe nada al instante
touch "$LOG_FILE"

echo "============================================================"
echo "Iniciando Backend..."
echo "Logs de esta sesión se guardarán en: $LOG_FILE"
echo "Presiona Ctrl+C para detener todos los procesos."
echo "============================================================"

# --- Función de Limpieza ---
# Esta función se ejecutará cuando se presione Ctrl+C
cleanup() {
    echo ""
    echo "¡Señal de detención recibida! Limpiando procesos..."
    # Mata al proceso del worker y al de la API usando sus PIDs
    # El '|| true' es para evitar errores si el proceso ya no existe
    kill $WORKER_PID || true
    kill $API_PID || true
    kill $TUNNEL_PID || true
    echo "Procesos detenidos. Saliendo."
    exit 0
}

# --- Atrapar la Señal ---
# Le decimos al script que ejecute la función 'cleanup' cuando reciba
# las señales INT (Ctrl+C) o TERM (detención estándar).
trap cleanup SIGINT SIGTERM

# --- Iniciar los Procesos ---
echo "Iniciando Pipeline Worker en segundo plano..."
# Redirigimos stdout y stderr al archivo de log
python3 /app/pipeline_worker.py >> "$LOG_FILE" 2>&1 &
# Guardamos el ID del Proceso (PID) del worker
WORKER_PID=$!

echo "Iniciando API Server en el puerto 8080..."
# Redirigimos stdout y stderr al archivo de log
python3 /app/api.py >> "$LOG_FILE" 2>&1 &
# Guardamos el PID de la API
API_PID=$!

echo "------------------------------------------------------------"
echo "Configurando Acceso Remoto (Cloudflare Tunnel)..."

if [ -n "$CLOUDFLARE_TOKEN" ]; then
    echo "✅ Token de Cloudflare detectado. Iniciando Túnel Fijo..."
    cloudflared tunnel run --token "$CLOUDFLARE_TOKEN" >> /app/logs/tunnel.log 2>&1 &
    TUNNEL_PID=$!
    echo "Túnel Fijo iniciado (PID: $TUNNEL_PID). Tu URL debería estar activa en breve."
else
    echo "⚠️  No se detectó CLOUDFLARE_TOKEN. Iniciando Túnel Ad-hoc (URL aleatoria)..."
    cloudflared tunnel --url http://localhost:8000 >> /app/logs/tunnel.log 2>&1 &
    TUNNEL_PID=$!
    echo "Túnel Ad-hoc iniciado (PID: $TUNNEL_PID). Busca la URL en /app/logs/tunnel.log"
fi

echo ""
echo "Mostrando logs en tiempo real. Presiona Ctrl+C para salir."
echo "------------------------------------------------------------"

# 'tail -f' seguirá el archivo de log y mostrará las nuevas líneas.
# Se ejecuta en primer plano, manteniendo el script vivo.
# Al presionar Ctrl+C, 'tail' se detiene y el trap de limpieza se activa.
tail -f "$LOG_FILE"
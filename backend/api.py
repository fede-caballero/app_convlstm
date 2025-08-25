import os
import json
import logging 
from datetime import datetime
from flask import Flask, jsonify

from config import STATUS_FILE_PATH, OUTPUT_DIR


app = Flask(__name__)
logging.basicConfig(level=logging.INFO), format='%(asctime)s - %(levelname)s - %(message)s'

# Endpoints de la API
@app.route("/api/status")
def get_status():
    logging.info("Request recibido en /api/status")
    try:
        if not os.path.exists(STATUS_FILE_PATH):
            # Si el archivo no existe, el worker probablemente no ha escrito su primer estado
            return jsonify({
                "status": "INITIALIZING",
                "message": "Status file not found. The worker might be starting."
            }), 404
        with open(STATUS_FILE_PATH, 'r') as f:
            status_data = json.load(f)
        return jsonify(status_data)
    
    except Exception as e:
        logging.error(f"Error al leer el archivo de estado: {e}")
        return jsonify({
            "status": "ERROR",
            "message": f"Failed to read status file: {str(e)}"
        }), 500
    
@app.route("/api/latest_prediction")
def get_latest_prediction():
    logging.info("Request recibido en /api/latest_prediction")
    try:
        # 1. Buscar todos los directorios de predicciones
        if not os.path.exists(OUTPUT_DIR):
            return jsonify({"error": "Prediction directory not found."}), 404
        
        prediction_sets = [d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))]

        if not prediction_sets:
            return jsonify({
                "message": "No predictions available yet.",
                "available_files": []
            })
        
        # 2. Encontrar el más reciente ordenando por nombre (timestamp)
        latest_set_dir = sorted(prediction_sets, reverse=True)[0]
        full_path = os.path.join(OUTPUT_DIR, latest_set_dir)

        # 3. Listar los archivos dentro de ese directorio
        prediction_files = sorted([f for f in os.listdir(full_path) if f.endswith('.nc')])

        # --- TAREA PENDIENTE (la haremos más adelante) ---
        # Por ahora, solo devolvemos la lista de archivos.
        # En el futuro, aquí leeremos uno de estos .nc y lo convertiremos a GeoJSON.

        return jsonify({
            "prediction_set_id": latest_set_dir,
            "available_files": prediction_files,
            "message": "GeoJSON conversion not implemented yet."
        })
    
    except Exception as e:
        logging.error(f"Error al obtener la última predicción: {e}")
        return jsonify({
            "error": "An internal error occurred."
        }) , 500

if __name__ == "__main__":
    logging.info("Iniciando servidor Flask API en modo de desarrollo...")
    # Escucha en 0.0.0.0 para ser accesible desde fuera del contenedor
    app.run(host='0.0.0.0', port=8080, debug=True)
    
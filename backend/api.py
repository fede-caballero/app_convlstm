import os
import json
import logging
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import STATUS_FILE_PATH, IMAGE_OUTPUT_DIR

app = Flask(__name__)
CORS(app) # Habilitar CORS para todas las rutas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Endpoint para servir las imágenes generadas
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_OUTPUT_DIR, filename)

# Endpoints de la API
@app.route("/api/status")
def get_status():
    logging.info("Request recibido en /api/status")
    try:
        if not os.path.exists(STATUS_FILE_PATH):
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

@app.route("/api/images")
def get_images():
    logging.info("Request recibido en /api/images")
    try:
        if not os.path.exists(IMAGE_OUTPUT_DIR):
            return jsonify({"input_images": [], "prediction_images": [], "message": "Image output directory not found."}), 404

        all_files = [f for f in os.listdir(IMAGE_OUTPUT_DIR) if f.endswith('.png')]
        
        input_images = sorted([f for f in all_files if f.startswith('INPUT_')], reverse=True)
        prediction_images = sorted([f for f in all_files if f.startswith('PRED_')], reverse=True)

        # Construir las URLs completas
        base_url = "/images/"
        input_urls = [base_url + f for f in input_images]
        prediction_urls = [base_url + f for f in prediction_images]

        return jsonify({
            "input_images": input_urls,
            "prediction_images": prediction_urls
        })
    except Exception as e:
        logging.error(f"Error al listar las imágenes: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

if __name__ == "__main__":
    logging.info("Iniciando servidor Flask API en modo de desarrollo...")
    app.run(host='0.0.0.0', port=8080, debug=True)
    
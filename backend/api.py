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
        
        input_images_names = sorted([f for f in all_files if f.startswith('INPUT_')], reverse=True)
        prediction_images_names = sorted([f for f in all_files if f.startswith('PRED_')], reverse=True)

        base_url = "/images/"
        
        def create_image_data(filenames):
            image_data_list = []
            for filename in filenames:
                json_path = os.path.join(IMAGE_OUTPUT_DIR, f"{filename}.json")
                bounds = None
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r') as f:
                            data = json.load(f)
                            bounds = data.get('bounds')
                    except Exception as e:
                        logging.warning(f"No se pudo leer o parsear el JSON '{json_path}': {e}")
                else:
                    logging.warning(f"No se encontró el archivo de coordenadas para {filename}")
                
                # Solo añadir si tenemos coordenadas, para asegurar que el mapa funcione
                if bounds:
                    image_data_list.append({
                        "url": base_url + filename,
                        "bounds": bounds
                    })
            return image_data_list

        return jsonify({
            "input_images": create_image_data(input_images_names),
            "prediction_images": create_image_data(prediction_images_names)
        })

    except Exception as e:
        logging.error(f"Error al listar las imágenes: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

if __name__ == "__main__":
    logging.info("Iniciando servidor Flask API en modo de desarrollo...")
    app.run(host='0.0.0.0', port=8080, debug=True)
    
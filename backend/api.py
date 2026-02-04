import os
import json
import logging
import sqlite3
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from config import STATUS_FILE_PATH, IMAGE_OUTPUT_DIR, DB_PATH
from datetime import datetime, timedelta
import auth

app = Flask(__name__)
CORS(app) # Habilitar CORS para todas las rutas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Auth Endpoints ---
@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    # Por seguridad, solo permitimos crear 'visitor' por defecto. 
    # Admin se debe crear manualmente o con un token especial (simplificado para este caso)
    role = data.get('role', 'visitor') 

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        hashed_pw = auth.get_password_hash(password)
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, hashed_pw, role))
        conn.commit()
        return jsonify({"message": "User created successfully"}), 201
    except sqlite3.IntegrityError:
        logging.warning(f"Intento de registro duplicado para usuario: {username}")
        return jsonify({"error": "Username already exists"}), 400
    except Exception as e:
        logging.error(f"Error CRÍTICO en registro: {e}", exc_info=True)
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, role, id FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if not user or not auth.verify_password(password, user[0]):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = auth.create_access_token(data={"sub": username, "role": user[1], "id": user[2]})
    return jsonify({"access_token": access_token, "token_type": "bearer", "role": user[1], "username": username})

@app.route('/auth/me', methods=['GET'])
def me():
    token = request.headers.get('Authorization')
    if not token or not token.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    token = token.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload:
        return jsonify({"error": "Invalid token"}), 401
        
    return jsonify(payload)

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
        
        # --- INPUT IMAGES (Last 3) ---
        input_images_names = sorted([f for f in all_files if f.startswith('INPUT_')], reverse=True)[:3]
        input_images_names.sort() # Chronological order

        # --- PREDICTION IMAGES (Last 2 runs, 5th frame only) ---
        # Filename format: PRED_<RUN_ID>_<FORECAST_TIME>.png
        # Example: PRED_20231027-160000_20231027_161500.png
        
        pred_files = [f for f in all_files if f.startswith('PRED_')]
        runs = {}

        for f in pred_files:
            try:
                # Remove prefix and extension
                parts = f.replace('PRED_', '').replace('.png', '').split('_')
                # parts[0] is RUN_ID (e.g. 20231027-160000)
                # parts[1] is FORECAST_DATE (e.g. 20231027)
                # parts[2] is FORECAST_TIME (e.g. 161500)
                
                # Handle potential legacy filenames (without RUN_ID) gracefully
                if len(parts) >= 3:
                    run_id = parts[0]
                    forecast_ts = f"{parts[1]}_{parts[2]}"
                else:
                    # Legacy file, ignore or treat as separate run
                    continue

                if run_id not in runs:
                    runs[run_id] = []
                runs[run_id].append(f)
            except Exception as e:
                logging.warning(f"Error parsing filename {f}: {e}")

        # Sort runs by ID (timestamp) and take THE LATEST ONE (most recent forecast)
        sorted_run_ids = sorted(runs.keys())
        
        selected_predictions = []
        if sorted_run_ids:
            latest_run_id = sorted_run_ids[-1]
            # Take ALL frames from the latest run to show full evolution
            selected_predictions = sorted(runs[latest_run_id])

        base_url = "/images/"
        
        def create_image_data(filenames, is_prediction=False):
            image_data_list = []
            for filename in filenames:
                json_path = os.path.join(IMAGE_OUTPUT_DIR, f"{filename}.json")
                bounds = None
                target_time = None
                
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r') as f:
                            data = json.load(f)
                            bounds = data.get('bounds')
                    except Exception as e:
                        logging.warning(f"No se pudo leer o parsear el JSON '{json_path}': {e}")
                
                # Calculate Target Time (UTC-3)
                try:
                    ts_str = None
                    if is_prediction:
                        # PRED_<RUN_ID>_<FORECAST_TIME>.png
                        parts = filename.replace('PRED_', '').replace('.png', '').split('_')
                        if len(parts) >= 3:
                            ts_str = f"{parts[1]}{parts[2]}" # YYYYMMDDHHMMSS
                    else:
                        # INPUT_<TIMESTAMP>.png
                        # Example: INPUT_20080305010845.png
                        parts = filename.replace('INPUT_', '').replace('.png', '').split('_')
                        if len(parts) >= 1:
                            ts_str = parts[0] # 20080305010845

                    if ts_str and len(ts_str) >= 12:
                        # Parse UTC timestamp
                        dt_utc = datetime.strptime(ts_str[:14], "%Y%m%d%H%M%S")
                        # Adjust to UTC-3
                        dt_local = dt_utc - timedelta(hours=3)
                        # Format as DD/MM HH:MM for context
                        target_time = dt_local.strftime("%d/%m %H:%M")
                        
                except Exception as e:
                    logging.warning(f"Error parsing time for {filename}: {e}")

                if bounds:
                    item = {
                        "url": base_url + filename,
                        "bounds": bounds
                    }
                    if target_time:
                        item["target_time"] = target_time
                    image_data_list.append(item)
            return image_data_list

        return jsonify({
            "input_images": create_image_data(input_images_names, is_prediction=False),
            "prediction_images": create_image_data(selected_predictions, is_prediction=True)
        })

    except Exception as e:
        logging.error(f"Error al listar las imágenes: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

@app.route("/api/upload_mdv", methods=['POST'])
def upload_mdv():
    """
    Endpoint para subir archivos MDV.
    Uso: curl -X POST -F "file=@/ruta/al/archivo.mdv" http://host:port/api/upload_mdv
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and file.filename.endswith('.mdv'):
        try:
            # Asegurar que el directorio existe
            from config import MDV_INBOX_DIR
            os.makedirs(MDV_INBOX_DIR, exist_ok=True)
            
            filename = os.path.basename(file.filename)
            save_path = os.path.join(MDV_INBOX_DIR, filename)
            file.save(save_path)
            
            logging.info(f"Archivo MDV recibido y guardado: {save_path}")
            return jsonify({"message": f"File {filename} uploaded successfully", "path": save_path}), 201
        except Exception as e:
            logging.error(f"Error al guardar el archivo MDV: {e}")
            return jsonify({"error": "Failed to save file"}), 500
    else:
        return jsonify({"error": "Invalid file type. Only .mdv allowed"}), 400

if __name__ == "__main__":
    from database import init_db
    init_db() # Asegurar que la DB existe al iniciar la API
    


    logging.info("Iniciando servidor Flask API en modo de desarrollo...")
    app.run(host='0.0.0.0', port=8000, debug=True)

# --- Comments Endpoints ---

@app.route('/api/comments', methods=['POST'])
def create_comment():
    # 1. Verificar Auth & Rol Admin
    token = request.headers.get('Authorization')
    if not token or not token.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    token = token.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload or payload.get('role') != 'admin':
        return jsonify({"error": "Unauthorized: Admins only"}), 403

    # 2. Obtener datos
    data = request.get_json()
    content = data.get('content')
    if not content:
        return jsonify({"error": "Content required"}), 400

    author_id = payload.get('id')
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 3. Desactivar comentarios anteriores (solo 1 activo a la vez)
        cursor.execute("UPDATE comments SET is_active = 0 WHERE is_active = 1")
        
        # 4. Insertar nuevo
        cursor.execute('''
            INSERT INTO comments (content, author_id, created_at, is_active)
            VALUES (?, ?, ?, 1)
        ''', (content, author_id, created_at))
        
        conn.commit()
        return jsonify({"message": "Comment posted successfully"}), 201
    except Exception as e:
        logging.error(f"Error posting comment: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/api/comments/latest', methods=['GET'])
def get_latest_comment():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT content, created_at, username 
            FROM comments 
            JOIN users ON comments.author_id = users.id 
            WHERE is_active = 1 
            ORDER BY created_at DESC 
            LIMIT 1
        ''')
        row = cursor.fetchone()
        
        if row:
            return jsonify({
                "content": row[0],
                "created_at": row[1],
                "author": row[2]
            })
        else:
            return jsonify(None), 200 # No content, return null (handled by frontend)
    except Exception as e:
        logging.error(f"Error fetching comment: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()
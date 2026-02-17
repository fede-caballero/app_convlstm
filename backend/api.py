import re
import os
import json
import logging
import sqlite3
from flask import Flask, jsonify, send_from_directory, request
from werkzeug.utils import secure_filename
from flask_cors import CORS
from config import STATUS_FILE_PATH, IMAGE_OUTPUT_DIR, DB_PATH, FRONTEND_URL
from datetime import datetime, timedelta, timezone
import auth

app = Flask(__name__)
REPORTS_UPLOAD_DIR = os.path.join(os.path.dirname(DB_PATH), 'uploads')
os.makedirs(REPORTS_UPLOAD_DIR, exist_ok=True)

# Security: Restrict CORS to frontend domain
# If FRONTEND_URL is "*", allow all. Otherwise, allow specified origins.
origins_list = [FRONTEND_URL]
if FRONTEND_URL == "*":
    origins_list = "*"
else:
    # Add localhost for dev and Vercel app for prod
    origins_list = [
        "http://localhost:3000",
        "https://app-convlstm.vercel.app",
        "https://hail-cast.vercel.app",
        FRONTEND_URL
    ]

CORS(app, origins=origins_list, supports_credentials=True)

# Initialize DB on module load (ensures migrations run in production/gunicorn)
from database import init_db
init_db()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Auth Endpoints ---
import auth
import email_service
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# --- Auth Endpoints ---
@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    
    # Por seguridad, solo permitimos crear 'visitor' por defecto. 
    role = data.get('role', 'visitor') 

    if not username or not password or not email:
        return jsonify({"error": "Username, password and email required"}), 400
        
    # Validation
    if len(password) < 8 or not re.search(r"\d", password) or not re.search(r"[a-zA-Z]", password):
        return jsonify({"error": "Password must be at least 8 characters long and contain both letters and numbers."}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        hashed_pw = auth.get_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, first_name, last_name, role) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, hashed_pw, email, first_name, last_name, role))
        conn.commit()
        
        # Send Welcome Email
        email_service.send_welcome_email(email, first_name or username)
        
        return jsonify({"message": "User created successfully"}), 201
    except sqlite3.IntegrityError as e:
        logging.warning(f"Intento de registro duplicado: {e}")
        if "email" in str(e):
            return jsonify({"error": "Email already exists"}), 400
        return jsonify({"error": "Username already exists"}), 400
    except Exception as e:
        logging.error(f"Error CRÍTICO en registro: {e}", exc_info=True)
        return jsonify({"error": f"Internal error: {str(e)}"}), 500
    finally:
        conn.close()
    


@app.route('/auth/google', methods=['POST'])
def google_login():
    data = request.get_json()
    token = data.get('credential')
    client_id = data.get('client_id') # Provided by frontend

    if not token:
        return jsonify({"error": "No token provided"}), 400

    try:
        # Verify token
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        
        # Get user info
        google_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', '')
        picture = idinfo.get('picture', '')
        given_name = idinfo.get('given_name', '')
        family_name = idinfo.get('family_name', '')
        
        # Check if user exists
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, role, username FROM users WHERE google_id = ? OR email = ?", (google_id, email))
        user_row = cursor.fetchone()
        
        if user_row:
            # Login existing user
            user_id, role, username = user_row
            
            # Link google_id if matched by email but no google_id yet
            cursor.execute("UPDATE users SET google_id = ?, picture = ? WHERE id = ?", (google_id, picture, user_id))
            conn.commit()
            
        else:
            # Register new user
            username = email.split('@')[0] # Default username from email
            # Check if username exists, append if so
            cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                username = f"{username}_{google_id[:4]}"
            
            cursor.execute("""
                INSERT INTO users (username, email, google_id, first_name, last_name, picture, role, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, 'visitor', 'GOOGLE_OAUTH')
            """, (username, email, google_id, given_name, family_name, picture))
            conn.commit()
            
            user_id = cursor.lastrowid
            role = 'visitor'
            
            # Send welcome email for new google users too
            email_service.send_welcome_email(email, given_name or name)

        conn.close()
        
        # Generate our JWT
        access_token = auth.create_access_token(data={"sub": username, "role": role, "id": user_id}, expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES))
        return jsonify({
            "access_token": access_token, 
            "token_type": "bearer", 
            "role": role, 
            "username": username,
            "picture": picture
        })

    except ValueError as e:
        # Invalid token
        logging.error(f"Google Token Verification Error: {e}")
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        logging.error(f"Google Login Error: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

# --- User Location Endpoint ---
@app.route('/api/user/location', methods=['POST'])
def update_user_location():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401
    
    token = auth_header.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload:
        return jsonify({"error": "Invalid token"}), 401
        
    user_id = payload.get('id')
    data = request.get_json()
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    if lat is None or lon is None:
        return jsonify({"error": "Latitude and longitude required"}), 400
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            UPDATE users 
            SET latitude = ?, longitude = ?, last_location_update = ?
            WHERE id = ?
        """, (lat, lon, now, user_id))
        
        conn.commit()
        return jsonify({"message": "Location updated"}), 200
    except Exception as e:
        logging.error(f"Error updating user location: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username_or_email = data.get('username')
    password = data.get('password')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, role, id, username FROM users WHERE username = ? OR email = ?", (username_or_email, username_or_email))
    user = cursor.fetchone()
    conn.close()

    if not user or not auth.verify_password(password, user[0]):
        return jsonify({"error": "Invalid credentials"}), 401

    real_username = user[3]
    real_username = user[3]
    access_token = auth.create_access_token(data={"sub": real_username, "role": user[1], "id": user[2]}, expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES))
    return jsonify({"access_token": access_token, "token_type": "bearer", "role": user[1], "username": real_username})

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

@app.route('/api/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(REPORTS_UPLOAD_DIR, filename)

# --- Push Notifications Endpoints ---
from config import VAPID_PRIVATE_KEY, VAPID_CLAIM_EMAIL
from pywebpush import webpush, WebPushException
# We need Vapid to derive the public key. Try importing from py_vapid or pywebpush.
try:
    from py_vapid import Vapid
except ImportError:
    # Fallback or error
    logging.error("Could not import Vapid from py_vapid")
    Vapid = None

@app.route('/api/notifications/vapid-public-key', methods=['GET'])
def get_vapid_public_key():
    try:
        if Vapid is None:
             return jsonify({"error": "Server missing 'py-vapid' library. Please rebuild backend image."}), 500
        
        if not VAPID_PRIVATE_KEY:
             return jsonify({"error": "VAPID_PRIVATE_KEY not configured on server."}), 500

        # Load Vapid from PEM string
        # Vapid.from_pem expects bytes
        vapid = Vapid.from_pem(VAPID_PRIVATE_KEY.encode('utf-8'))
        
        # Get the Application Server Key (Public Key)
        # py-vapid provides this as a property, usually returning bytes.
        # We need to ensure it's base64url encoded for the frontend.
        
        # Check if we can get the raw public key bytes or the pre-encoded key
        if hasattr(vapid, "application_server_key"):
             # This property often returns the raw bytes (uncompressed point)
             raw_pub = vapid.application_server_key
        else:
             # Fallback: Serialize manually if needed (should not happen with standard py-vapid)
             # But wait, debug showed public_key is an object.
             # let's try to get the raw bytes from the object if needed.
             pass

        # Actually, the most reliable way with py-vapid is:
        # It calculates the public key on initialization.
        # Inspecting py-vapid source:
        # The public key is an EC point.
        # We need the UNCOMPRESSED format (0x04 + x + y).
        
        from cryptography.hazmat.primitives import serialization
        
        public_key_bytes = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        import base64
        # Encode to URL-Safe Base64
        vapid_public_key = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
        
        return jsonify({"publicKey": vapid_public_key}), 200
    except Exception as e:
        logging.error(f"Error deriving public key: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/subscribe', methods=['POST'])
def subscribe_push():
    data = request.get_json()
    subscription = data.get('subscription') # Expecting standard PushSubscription object
    if not subscription:
        return jsonify({"error": "No subscription data"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user is logged in (optional, but good for linking)
    user_id = None
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = auth.decode_access_token(token)
            if payload:
                user_id = payload.get('id')
        except:
            pass

    try:
        endpoint = subscription.get('endpoint')
        keys = subscription.get('keys', {})
        p256dh = keys.get('p256dh')
        auth_key = keys.get('auth')

        if not endpoint or not p256dh or not auth_key:
             return jsonify({"error": "Invalid subscription object"}), 400

        # Upsert or Insert (SQLite UPSERT syntax or basic check)
        # Using INSERT OR REPLACE to update keys if endpoint exists
        cursor.execute("""
            INSERT OR REPLACE INTO push_subscriptions (user_id, endpoint, p256dh, auth)
            VALUES (?, ?, ?, ?)
        """, (user_id, endpoint, p256dh, auth_key))
        
        conn.commit()
        return jsonify({"message": "Subscribed successfully"}), 201
    except Exception as e:
        logging.error(f"Error subscribing to push: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/notifications/subscribe', methods=['DELETE'])
def unsubscribe_push():
    data = request.get_json()
    endpoint = data.get('endpoint')

    if not endpoint:
        return jsonify({"error": "Missing endpoint"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
        conn.commit()
        
        if cursor.rowcount == 0:
             return jsonify({"message": "Subscription not found"}), 404
             
        return jsonify({"message": "Unsubscribed successfully"}), 200
    except Exception as e:
        logging.error(f"Error unsubscribing: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

def _send_push_to_all(title, message, url):
    """
    Helper function to send push notifications to all subscribers.
    Used by both manual send endpoint and auto-send on comment.
    """
    logging.info(f"Initiating Push to All: {title} - {message}")
    
    notification_data = json.dumps({
        "title": title,
        "body": message,
        "url": url,
        "icon": "/icon-192x192.png"
    })

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions")
        subscriptions = cursor.fetchall()
        conn.close()
    except Exception as e:
        logging.error(f"DB Error fetching subs: {e}")
        return []

    if not subscriptions:
        logging.info("No subscriptions found.")
        return []

    results = []
    headers = {
        "TTL": "60",
        "Urgency": "high"
    }

    vapid_obj = None
    try:
        # Manual VAPID Signing Setup
        if Vapid is None:
             raise ImportError("py-vapid library not loaded")

        key_bytes = VAPID_PRIVATE_KEY.encode('utf-8')
        vapid_obj = Vapid.from_pem(key_bytes)
    except Exception as e:
        logging.error(f"VAPID Setup Error: {e}")
        # Continue? No, we need vapid_obj
        return []

    for sub in subscriptions:
        endpoint, p256dh, auth_key = sub
        subscription_info = {
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh, "auth": auth_key}
        }
        
        try:
            # Generate Headers per endpoint
            # Generate Headers per endpoint
            auth_headers = {}
            
            if vapid_obj and hasattr(vapid_obj, "get_authorization_header"):
                 header_value = vapid_obj.get_authorization_header(endpoint, VAPID_CLAIM_EMAIL)
                 if isinstance(header_value, (bytes, str)):
                     if isinstance(header_value, bytes):
                         header_value = header_value.decode('utf-8')
                     auth_headers = {"Authorization": header_value}
                 elif isinstance(header_value, dict):
                     auth_headers = header_value
            else:
                 # Fallback for older/different py-vapid versions
                 from urllib.parse import urlparse
                 parsed = urlparse(endpoint)
                 aud = f"{parsed.scheme}://{parsed.netloc}"
                 claim = {"aud": aud, "sub": VAPID_CLAIM_EMAIL}
                 
                 token = vapid_obj.sign(claim)
                 
                 if isinstance(token, dict):
                     auth_headers = token
                 else:
                     if isinstance(token, bytes):
                         token = token.decode('utf-8')
                     if "vapid t=" in token:
                         auth_headers = {"Authorization": token}
                     else:
                         auth_headers = {"Authorization": f"WebPush {token}"}
            
            final_headers = headers.copy()
            final_headers.update(auth_headers)

            webpush(
                subscription_info=subscription_info,
                data=notification_data,
                vapid_private_key=None,
                vapid_claims=None,
                headers=final_headers
            )
            results.append({"endpoint": endpoint, "status": "sent"})
        except WebPushException as e:
            logging.error(f"Push error for {endpoint}: {e}")
            if "410" in str(e) or "404" in str(e):
                 # Todo: Delete from DB
                 pass
            results.append({"endpoint": endpoint, "status": "failed", "error": str(e)})
        except Exception as e:
             logging.error(f"Generic Push error for {endpoint}: {e}")
             results.append({"endpoint": endpoint, "status": "failed", "error": str(e)})

    logging.info(f"Push Summary: Sent {len([r for r in results if r['status']=='sent'])}/{len(subscriptions)}")
    return results

@app.route('/api/notifications/send', methods=['POST'])
def send_push_notification():
    # Admin only check
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401
    
    token = auth_header.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload or payload.get('role') not in ['admin', 'superadmin']:
        return jsonify({"error": "Admins only"}), 403

    data = request.get_json()
    message = data.get('message', 'Alerta Meteorológica')
    title = data.get('title', 'Alerta')
    url = data.get('url', '/')

    results = _send_push_to_all(title, message, url)
    return jsonify({"results": results}), 200

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
                            cells = data.get('cells')
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
                        "bounds": bounds,
                        "cells": cells
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

# --- Comments Endpoints ---

@app.route('/api/comments', methods=['GET'])
def get_comments():
    limit = request.args.get('limit', default=5, type=int)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Return dict-like rows
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT comments.id, content, created_at, username as author
            FROM comments 
            JOIN users ON comments.author_id = users.id 
            WHERE is_active = 1 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        comments = [dict(row) for row in rows]
        return jsonify(comments), 200
    except Exception as e:
        logging.error(f"Error fetching comments: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()

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
    # Use timezone-aware UTC timestamp
    created_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # NO des-activamos comentarios anteriores. Permitimos historial.
        
        # 4. Insertar nuevo
        cursor.execute('''
            INSERT INTO comments (content, author_id, created_at, is_active)
            VALUES (?, ?, ?, 1)
        ''', (content, author_id, created_at))
        
        conn.commit()
        
        # --- AUTO-PUSH NOTIFICATION ---
        try:
            # Launch in background thread ideally, but for now blocking is fine (it's fast-ish)
            logging.info("Auto-triggering push for new comment...")
            _send_push_to_all(title="Nueva alerta", message=content, url="/")
        except Exception as e:
            logging.error(f"Failed to auto-send push: {e}")

        return jsonify({"message": "Comment posted successfully"}), 201
    except Exception as e:
        logging.error(f"Error posting comment: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/api/comments/<int:comment_id>', methods=['PUT', 'DELETE'])
def manage_comment(comment_id):
    # 1. Verificar Auth & Rol Admin
    token = request.headers.get('Authorization')
    if not token or not token.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    token = token.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload or payload.get('role') != 'admin':
        return jsonify({"error": "Unauthorized: Admins only"}), 403

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        if request.method == 'DELETE':
            # Soft Delete
            cursor.execute("UPDATE comments SET is_active = 0 WHERE id = ?", (comment_id,))
            if cursor.rowcount == 0:
                return jsonify({"error": "Comment not found"}), 404
            conn.commit()
            return jsonify({"message": "Comment deleted"}), 200

    finally:
        conn.close()

# --- Reports Endpoints (Crowdsourcing) ---

@app.route('/api/reports', methods=['GET'])
def get_reports():
    # Retrieve reports for the current operational day (8AM to 8AM)
    
    # Calculate "start of current operational day"
    # If now is before 8AM, start is yesterday 8AM.
    # If now is after 8AM, start is today 8AM.
    
    now_utc = datetime.now(timezone.utc)
    # Adjust to Local Time (UTC-3) for logic, then convert back to UTC for query if needed?
    # Actually, the user likely means 8AM Local Time.
    # Let's assume server ensures UTC in DB.
    # 8AM Argentina (UTC-3) = 11AM UTC.
    
    # Let's stick to UTC-3 logic for "Operational Day"
    now_local = now_utc - timedelta(hours=3)
    
    if now_local.hour < 8:
        start_local = now_local.replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=1)
    else:
        start_local = now_local.replace(hour=8, minute=0, second=0, microsecond=0)
        
    start_utc = start_local + timedelta(hours=3)
    cutoff_time = start_utc.isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Join with users to get username of reporter? Maybe useful.
        cursor.execute('''
            SELECT r.id, r.user_id, r.report_type, r.latitude, r.longitude, r.timestamp, r.description, r.image_url, u.username
            FROM weather_reports r
            LEFT JOIN users u ON r.user_id = u.id
            WHERE r.timestamp >= ?
            ORDER BY r.timestamp DESC
        ''', (cutoff_time,))
        
        rows = cursor.fetchall()
        reports = [dict(row) for row in rows]
        return jsonify(reports), 200
    except Exception as e:
        logging.error(f"Error fetching reports: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/api/reports', methods=['POST'])
def create_report():
    # 1. Verify Auth
    token = request.headers.get('Authorization')
    if not token or not token.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    token = token.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload:
        return jsonify({"error": "Invalid token"}), 401

    user_id = payload.get('id')
    
    # 2. Get Data
    # 2. Get Data (supports multipart/form-data)
    if 'report_type' not in request.form and not request.is_json:
        return jsonify({"error": "Content-Type must be application/json or multipart/form-data"}), 400

    report_type = request.form.get('report_type') or (request.json.get('report_type') if request.is_json else None)
    try:
        latitude = float(request.form.get('latitude') or (request.json.get('latitude') if request.is_json else 0))
        longitude = float(request.form.get('longitude') or (request.json.get('longitude') if request.is_json else 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Latitude/Longitude must be numbers"}), 400

    description = request.form.get('description', '') if not request.is_json else request.json.get('description', '')

    image_url = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
            save_path = os.path.join(REPORTS_UPLOAD_DIR, unique_filename)
            file.save(save_path)
            image_url = f"/api/uploads/{unique_filename}" # Use /api/uploads because vercel rewrites might handle it differently but let's stick to simple relative path?
            # Wait, api.py handles /uploads/*, but frontend usually proxies /api/* to api.py
            # If standard route is /uploads/..., let's check.
            # Usually users see /uploads/foo.png.
            # But api.py is usually behind /api reverse proxy or handles everything under /api.
            # Let's map it to /api/uploads/ in Flask and define route accordingly?
            # The route added above is @app.route('/uploads/<path:filename>').
            # If frontend calls /uploads/foo.png, it might not hit backend unless configured.
            # Let's use /api/uploads/ to be safe with standard proxy setups.
            image_url = f"/api/uploads/{unique_filename}"

    if not all([report_type, latitude, longitude]):
        return jsonify({"error": "Missing required fields (type, lat, lon)"}), 400

    # 3. Save
    timestamp = datetime.now(timezone.utc).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO weather_reports (user_id, report_type, latitude, longitude, timestamp, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, report_type, latitude, longitude, timestamp, description, image_url))
        conn.commit()
        return jsonify({"message": "Report submitted successfully", "image_url": image_url}), 201
    except Exception as e:
        logging.error(f"Error submitting report: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/api/reports/<int:report_id>', methods=['DELETE'])
def delete_report(report_id):
    # 1. Verify Auth & Admin Role
    token = request.headers.get('Authorization')
    if not token or not token.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    token = token.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload or payload.get('role') != 'admin':
        return jsonify({"error": "Unauthorized: Admins only"}), 403

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Check if report exists
        cursor.execute("SELECT id FROM weather_reports WHERE id = ?", (report_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Report not found"}), 404

        # Delete
        cursor.execute("DELETE FROM weather_reports WHERE id = ?", (report_id,))
        conn.commit()
        return jsonify({"message": "Report deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting report: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/api/reports/<int:report_id>', methods=['PUT'])
def update_report(report_id):
    # 1. Verify Auth
    token = request.headers.get('Authorization')
    if not token or not token.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    token = token.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload:
        return jsonify({"error": "Invalid token"}), 401

    user_id = payload.get('id')
    user_role = payload.get('role')

    # 2. Get Data
    description = request.form.get('description') or (request.json.get('description') if request.is_json else None)

    image_url = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
            save_path = os.path.join(REPORTS_UPLOAD_DIR, unique_filename)
            file.save(save_path)
            image_url = f"/api/uploads/{unique_filename}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # 3. Check Ownership
        cursor.execute("SELECT user_id, image_url FROM weather_reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Report not found"}), 404
        
        owner_id, current_image_url = row

        # Only owner can edit (Admins can delete, but maybe not edit content? Let's restrict to owner for now)
        if owner_id != user_id:
             return jsonify({"error": "Unauthorized: You can only edit your own reports"}), 403

        # 4. Update
        # If new image, use it. If not, keep old (unless maybe explicitly cleared? MVP: overwrite if new provided)
        final_image_url = image_url if image_url else current_image_url
        
        # If description is None (not provided), keep old? Or allow clearing?
        # If frontend sends description="", it means clear. If it sends nothing, maybe keep old.
        # Let's assume frontend sends strictly what it wants to set.
        # But wait, multipart/form-data might not send 'description' key if empty?
        # Let's update description ONLY if it's not None. If it's empty string, we set it to empty string.
        
        query_parts = []
        params = []

        if description is not None:
             query_parts.append("description = ?")
             params.append(description)
        
        if image_url is not None:
             query_parts.append("image_url = ?")
             params.append(image_url)

        if not query_parts:
             return jsonify({"message": "No changes detected"}), 200

        params.append(report_id)
        sql = f"UPDATE weather_reports SET {', '.join(query_parts)} WHERE id = ?"
        
        cursor.execute(sql, tuple(params))
        conn.commit()
        
        return jsonify({
            "message": "Report updated successfully", 
            "image_url": final_image_url,
            "description": description 
        }), 200

    except Exception as e:
        logging.error(f"Error updating report: {e}")
        return jsonify({"error": "Internal error"}), 500
    finally:
        conn.close()



if __name__ == "__main__":
    logging.info("Iniciando servidor Flask API en modo de desarrollo...")
    app.run(host='0.0.0.0', port=8000, debug=True)

# End of file
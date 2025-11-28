import os
import sqlite3
import logging
from config import DB_PATH

def init_db():
    """Inicializa la base de datos SQLite si no existe."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Tabla de predicciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                input_sequence_id TEXT,
                output_path TEXT,
                status TEXT
            )
        ''')
        
        # Tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'visitor'
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info(f"Base de datos verificada/inicializada en {DB_PATH}")
    except Exception as e:
        logging.error(f"Error al inicializar la base de datos: {e}")

def get_db_connection():
    """Retorna una conexión a la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

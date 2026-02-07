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
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT,
                first_name TEXT,
                last_name TEXT,
                google_id TEXT UNIQUE,
                picture TEXT,
                role TEXT NOT NULL DEFAULT 'visitor'
            )
        ''')

        # Migraciones: Agregar columnas si no existen (para bases de datos existentes)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE")
        except sqlite3.OperationalError:
            pass # Ya existe

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN google_id TEXT UNIQUE")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN picture TEXT")
        except sqlite3.OperationalError:
            pass


        # Tabla de comentarios de administrador
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                author_id INTEGER,
                created_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(author_id) REFERENCES users(id)
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

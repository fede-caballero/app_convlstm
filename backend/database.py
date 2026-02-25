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

        # Helper to safely add columns
        def add_column_if_not_exists(table, column, definition):
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            if column not in columns:
                try:
                    # SQLite 'ALTER TABLE' has limitations with UNIQUE.
                    # workaround: Add column without UNIQUE, then create index if needed.
                    is_unique = "UNIQUE" in definition.upper()
                    clean_definition = definition.replace("UNIQUE", "").replace("unique", "")
                    
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {clean_definition}")
                    logging.info(f"Columna '{column}' agregada a '{table}'")
                    
                    if is_unique:
                        index_name = f"idx_{table}_{column}"
                        cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
                        logging.info(f"Índice UNIQUE '{index_name}' creado")
                        
                except Exception as e:
                    logging.error(f"Error agregando columna '{column}' a '{table}': {e}")
            else:
                pass # Column already exists

        # Migrations
        add_column_if_not_exists("users", "email", "TEXT UNIQUE") # Will create index
        add_column_if_not_exists("users", "first_name", "TEXT")
        add_column_if_not_exists("users", "last_name", "TEXT")
        add_column_if_not_exists("users", "google_id", "TEXT UNIQUE") # Will create index
        add_column_if_not_exists("users", "picture", "TEXT")
        # Location & Proximity Alert Columns
        add_column_if_not_exists("users", "latitude", "REAL")
        add_column_if_not_exists("users", "longitude", "REAL")
        add_column_if_not_exists("users", "last_location_update", "TEXT")
        add_column_if_not_exists("users", "last_proximity_alert", "TEXT")

        add_column_if_not_exists("weather_reports", "image_url", "TEXT")


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

        # Tabla de reportes meteorológicos (Crowdsourcing)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                report_type TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                timestamp TEXT NOT NULL,
                description TEXT,
                image_url TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        # Tabla de suscripciones Push
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                alert_admin INTEGER DEFAULT 1,
                alert_proximity INTEGER DEFAULT 1,
                alert_aircraft INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # Migrations for existing DB instances
        add_column_if_not_exists("push_subscriptions", "latitude", "REAL")
        add_column_if_not_exists("push_subscriptions", "longitude", "REAL")
        add_column_if_not_exists("push_subscriptions", "alert_admin", "INTEGER DEFAULT 1")
        add_column_if_not_exists("push_subscriptions", "alert_proximity", "INTEGER DEFAULT 1")
        add_column_if_not_exists("push_subscriptions", "alert_aircraft", "INTEGER DEFAULT 0")
        
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

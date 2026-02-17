import sqlite3
import datetime
from database import DB_PATH

def analyze_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Total Users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # 2. Users created "yesterday" (assuming yesterday based on server time)
        # SQLite doesn't always have 'created_at' in users based on my previous read of init_db.
        # Let's check table info first.
        cursor.execute("PRAGMA table_info(users)")
        columns = [row['name'] for row in cursor.fetchall()]
        
        print(f"=== ANÁLISIS DE USUARIOS ===")
        print(f"Total de usuarios registrados: {total_users}")
        
        if 'created_at' in columns:
            # Calculate dates
            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = ?", (yesterday,))
            yesterday_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = ?", (today,))
            today_users = cursor.fetchone()[0]
            
            print(f"Usuarios creados AYER ({yesterday}): {yesterday_users}")
            print(f"Usuarios creados HOY ({today}): {today_users}")
            
            # List details for yesterday
            if yesterday_users > 0:
                print("\n--- Detalle Usuarios de Ayer ---")
                cursor.execute("SELECT username, email, provider_or_method FROM users WHERE date(created_at) = ?", (yesterday,))
                # Note: 'provider_or_method' might not exist, checking basic fields
                cursor.execute("SELECT username, email FROM users WHERE date(created_at) = ?", (yesterday,))
                for u in cursor.fetchall():
                    print(f"- {u['username']} ({u['email']})")
        else:
            print("\n[INFO] La tabla 'users' no tiene columna 'created_at', por lo que no se pueden filtrar por fecha.")
            print("Estructura actual de 'users':", columns)
            print("Sugerencia: Debemos agregar created_at en la próxima actualización.")
            
            # Show last 10 users as fallback
            print("\n--- Últimos 10 usuarios (por ID) ---")
            cursor.execute("SELECT id, username, email FROM users ORDER BY id DESC LIMIT 10")
            for u in cursor.fetchall():
                print(f"ID {u['id']}: {u['username']} ({u['email']})")

    except Exception as e:
        print(f"Error analizando DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_users()

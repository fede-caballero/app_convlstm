import sqlite3
import sys
import os
from database import DB_PATH

def promote_user(username):
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar si el usuario existe
        cursor.execute("SELECT id, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if not user:
            print(f"Error: User '{username}' not found.")
            conn.close()
            return

        if user[1] == 'admin':
            print(f"User '{username}' is already an admin.")
            conn.close()
            return

        # Actualizar rol
        cursor.execute("UPDATE users SET role = 'admin' WHERE username = ?", (username,))
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"Success: User '{username}' promoted to 'admin'.")
        else:
            print("Error: Failed to update user role.")
            
        conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python promote_admin.py <username>")
    else:
        promote_user(sys.argv[1])

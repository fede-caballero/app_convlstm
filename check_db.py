import sqlite3
import os

db_path = "backend/data/radar_history.db"

if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in DB:", tables)

    if ('push_subscriptions',) in tables:
        cursor.execute("SELECT id, alert_admin, alert_proximity, alert_aircraft FROM push_subscriptions")
        rows = cursor.fetchall()
        print(f"Total subscriptions: {len(rows)}")
        for r in rows:
            print(f"ID={r[0]}, admin={r[1]}, prox={r[2]}, aircraft={r[3]}")
    else:
        print("push_subscriptions table does not exist")

except Exception as e:
    print(f"DB Error: {e}")
finally:
    conn.close()

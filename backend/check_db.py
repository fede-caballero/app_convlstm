import sqlite3
import json

try:
    conn = sqlite3.connect('data/radar_history.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, endpoint, alert_admin, alert_proximity, alert_aircraft FROM push_subscriptions")
    rows = cursor.fetchall()
    print("Subscriptions:")
    for r in rows:
        print(f"ID={r[0]}, auth={r[1][:25]}..., admin={r[2]}, prox={r[3]}, aircraft={r[4]}")
except Exception as e:
    print(e)

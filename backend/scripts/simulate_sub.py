import requests
import json
import sqlite3
import os

print("=== SIMULATE FRONTEND SUBSCRIPTION ===")

# 1. Config
API_URL = "http://localhost:8000/api/notifications/subscribe"
DB_PATH = "/app/data/radar_history.db"

# Mock Subscription Object (Chrome-like)
mock_sub = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/TEST_ENDPOINT_123",
    "keys": {
        "p256dh": "BM_mock_p256dh_key_string_from_browser",
        "auth": "mock_auth_key"
    }
}

print(f"Target URL: {API_URL}")
print(f"Payload: {json.dumps(mock_sub, indent=2)}")

try:
    # 2. Send POST
    print("\nSending POST request...")
    resp = requests.post(API_URL, json={"subscription": mock_sub})
    
    print(f"Response Status: {resp.status_code}")
    print(f"Response Body: {resp.text}")

    if resp.status_code != 201:
        print("❌ API did not return 201 Created.")
        exit(1)

    # 3. Verify DB
    print("\nVerifying Database...")
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM push_subscriptions WHERE endpoint = ?", (mock_sub["endpoint"],))
    row = cursor.fetchone()
    conn.close()

    if row:
        print(f"✅ SUCCESS: Found subscription in DB: {row}")
    else:
        print("❌ FAILURE: Subscription NOT found in DB despite API 201.")

except Exception as e:
    print(f"❌ Error: {e}")

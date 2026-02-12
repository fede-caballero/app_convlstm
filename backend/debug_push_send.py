import sqlite3
import json
import logging
from config import VAPID_PRIVATE_KEY, VAPID_CLAIM_EMAIL, DB_PATH
from pywebpush import webpush, WebPushException

# Configure logging to see everything
logging.basicConfig(level=logging.DEBUG)

print("=== DEBUG PUSH SEND START ===")
print(f"DB Path: {DB_PATH}")
print(f"VAPID Email: {VAPID_CLAIM_EMAIL}")
print(f"VAPID Key Length: {len(VAPID_PRIVATE_KEY) if VAPID_PRIVATE_KEY else 'None'}")

if not VAPID_PRIVATE_KEY:
    print("❌ Critical: VAPID_PRIVATE_KEY is missing.")
    exit(1)

# 1. Fetch Subscriptions
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions")
    subscriptions = cursor.fetchall()
    conn.close()
    print(f"Found {len(subscriptions)} subscriptions.")
except Exception as e:
    print(f"❌ DB Error: {e}")
    exit(1)

if not subscriptions:
    print("⚠️ No subscriptions to test with.")
    exit(0)

# 2. Prepare Payload
notification_data = json.dumps({
    "title": "Debug Test",
    "body": "Testing from debug script",
    "url": "/"
})

headers = {
    "TTL": "60",
    "Urgency": "high"
}

# 3. Try Sending
for sub in subscriptions:
    endpoint, p256dh, auth_key = sub
    print(f"Testing subscription: {endpoint[:30]}...")
    
    subscription_info = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": p256dh,
            "auth": auth_key
        }
    }
    
    try:
        webpush(
            subscription_info=subscription_info,
            data=notification_data,
            vapid_private_key=VAPID_PRIVATE_KEY.encode('utf-8'),
            vapid_claims={"sub": VAPID_CLAIM_EMAIL},
            headers=headers
        )
        print("✅ Send Success!")
    except WebPushException as e:
        print(f"⚠️ WebPushException (Expected if sub invalid): {e}")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

print("=== DEBUG PUSH SEND END ===")

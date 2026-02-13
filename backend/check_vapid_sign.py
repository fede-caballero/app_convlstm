from py_vapid import Vapid
from config import VAPID_PRIVATE_KEY, VAPID_CLAIM_EMAIL
import logging

logging.basicConfig(level=logging.DEBUG)

print("Key available:", bool(VAPID_PRIVATE_KEY))

if not VAPID_PRIVATE_KEY:
    exit(1)

try:
    # 1. Load Vapid from PEM string (bytes)
    # This matches api.py current working logic
    vapid = Vapid.from_pem(VAPID_PRIVATE_KEY.encode('utf-8'))
    print("Vapid loaded successfully!")
    print(f"Public Key (raw): {vapid.public_key}")

    # 2. Try to generate headers
    claims = {"sub": VAPID_CLAIM_EMAIL}
    
    # Need mock subscription info
    mock_sub_info = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/foo",
        "keys": {"p256dh": "mock", "auth": "mock"}
    }
    
    headers = vapid.get_authorization_header(mock_sub_info["endpoint"], VAPID_CLAIM_EMAIL)
    # Or sign?
    # Inspect vapid object methods
    print("Methods available:", dir(vapid))
    
    # Try different ways to get headers
    # Some versions use get_authorization_header
    # Some versions require `sign` then construct header manually?

    # Trying typical py-vapid usage:
    # headers = vapid.sign(subscription_info, claims) ?? No
    
    # Re-check py-vapid documentation or source if possible via help()
    
    help(Vapid)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

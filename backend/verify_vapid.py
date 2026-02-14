import sys
import os

print(f"CWD: {os.getcwd()}")
sys.path.append(os.getcwd())

from py_vapid import Vapid
from pywebpush import webpush, WebPushException
import json
import logging

logging.basicConfig(level=logging.INFO)

# 1. Load Keys from Env / Config
try:
    try:
        from config import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIM_EMAIL
        print(f"✅ Loaded keys from config.py")
    except ImportError:
        # Fallback: maybe we are in backend/ and config is here
        sys.path.append(os.path.join(os.getcwd(), 'backend'))
        from backend.config import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIM_EMAIL
        print(f"✅ Loaded keys from backend.config")

    print(f"Public Key (Config): {VAPID_PUBLIC_KEY[:10]}...")
    print(f"Private Key (Config): {VAPID_PRIVATE_KEY[:10]}...")
except ImportError as e:
    print(f"❌ Could not import keys from config.py: {e}")
    # Try reading .env manually?
    exit(1)

# 2. Test Key Validity
try:
    key_bytes = VAPID_PRIVATE_KEY.encode('utf-8')
    vapid_obj = Vapid.from_pem(key_bytes)
    print("✅ Private Key is valid PEM.")
    
    # Check if public key matches derived public key
    derived_public = vapid_obj.public_key.strip() # specific to library version
    # Actually py-vapid public_key implementation varies.
    # Let's just try to sign something.
    header = vapid_obj.get_authorization_header("https://fcm.googleapis.com", VAPID_CLAIM_EMAIL)
    print(f"✅ Signed Header successfully: {str(header)[:20]}...")
except Exception as e:
    print(f"❌ Key Validation Failed: {e}")
    exit(1)

print("\n=== VAPID Configuration seems OK ===")
print("If mobile steps 1-7 passed, the subscription IS in the DB.")
print("The issue is likely the delivery itself.")

import sys
import os
import json
import logging
import traceback

logging.basicConfig(level=logging.INFO)
sys.path.append(os.path.abspath('backend'))

try:
    from core.config import VAPID_PRIVATE_KEY, VAPID_CLAIM_EMAIL
    from py_vapid import Vapid
    
    print(f"Key loaded? {bool(VAPID_PRIVATE_KEY)}")
    if VAPID_PRIVATE_KEY:
        vapid_obj = Vapid.from_pem(VAPID_PRIVATE_KEY.encode('utf-8'))
        print("Vapid Object successfully initialized")
    else:
        print("NO VAPID KEY FOUND in environment.")

except Exception as e:
    print(f"Crash: {e}")
    traceback.print_exc()

import sys
import os
import json
import logging
import traceback

logging.basicConfig(level=logging.INFO)
sys.path.append(os.path.abspath('backend'))

from config import VAPID_PRIVATE_KEY, VAPID_CLAIM_EMAIL
from pywebpush import webpush

print(f"Key loaded: {bool(VAPID_PRIVATE_KEY)}")

try:
    if not VAPID_PRIVATE_KEY:
        print("NO KEY")
    else:
        print("Length", len(VAPID_PRIVATE_KEY))
except Exception as e:
    print(f"VAPID Crash: {e}")
    traceback.print_exc()

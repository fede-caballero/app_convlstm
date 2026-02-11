import os
import sys

print("=== CHECK SERVER ENV START ===")

# 1. Check Raw Env Var
raw_key = os.getenv("VAPID_PRIVATE_KEY")
print(f"1. Raw VAPID_PRIVATE_KEY (from os.getenv): {'[PRESENT]' if raw_key else '[MISSING]'}")
if raw_key:
    print(f"   Length: {len(raw_key)}")
    print(f"   First 10 chars: {raw_key[:10]!r}")
    print(f"   Last 10 chars: {raw_key[-10:]!r}")
else:
    print("   CRITICAL: Env var is missing or empty.")

# 2. Check py-vapid installation
try:
    from py_vapid import Vapid
    print("2. py-vapid library: [INSTALLED]")
except ImportError as e:
    print(f"2. py-vapid library: [MISSING] - Error: {e}")
    print("   CRITICAL: You need to rebuild the container to install dependencies.")

# 3. Check config.py logic
try:
    import config
    print("3. config.py: [IMPORTED]")
    processed_key = config.VAPID_PRIVATE_KEY
    print(f"   Processed Key in config: {'[PRESENT]' if processed_key else '[MISSING]'}")
    if processed_key:
        print(f"   Length: {len(processed_key)}")
        print(f"   Starts with: {processed_key[:20]!r}")
        if "\\n" in processed_key:
             print("   WARNING: Literal '\\n' found in processed key. Replacement failed?")
        if "\n" in processed_key:
             print("   SUCCESS: Real newline characters found.")
        if '"' in processed_key or "'" in processed_key:
             print("   WARNING: Quotes found in processed key. Strip failed?")
except Exception as e:
    print(f"3. config.py: [ERROR] - {e}")

# 4. Try parsing
if 'Vapid' in locals() and 'processed_key' in locals() and processed_key:
    try:
        vapid = Vapid.from_pem(processed_key.encode('utf-8'))
        print("4. VAPID Key Parsing: [SUCCESS]")
        print(f"   Public Key: {vapid.public_key}")
    except Exception as e:
        print(f"4. VAPID Key Parsing: [FAILED] - {e}")

print("=== CHECK SERVER ENV END ===")

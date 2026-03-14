from py_vapid import Vapid
import base64

# Use exact key logic from config.py/script
VAPID_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgKNXZKnXqooazHJhG\nte+HO4pGOYNox02KnfMbQRaPPx2hRANCAAQiwmI0eCXzBohLvPYlUzj/LLqyZy/r\n/kFuv/v8UWVh1jCrgO1itX+6rXpyxWlziJN+uvY7tw0L0F/l49T1453Q\n-----END PRIVATE KEY-----"

processed_key = VAPID_PRIVATE_KEY.strip('"').strip("'").replace("\\n", "\n")

vapid = Vapid.from_pem(processed_key.encode('utf-8'))

print(f"Type of public_key: {type(vapid.public_key)}")
print(f"Value of public_key: {vapid.public_key}")

# Try encoding it for safe transport
if isinstance(vapid.public_key, bytes):
    print("It is bytes.")
    b64 = base64.b64encode(vapid.public_key).decode('utf-8')
    print(f"Standard Base64: {b64}")
    b64url = base64.urlsafe_b64encode(vapid.public_key).decode('utf-8')
    print(f"URL Safe Base64: {b64url}")
else:
    print("It is NOT bytes (maybe already an object or string?)")

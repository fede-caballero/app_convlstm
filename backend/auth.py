import os
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Configuración
from config import SECRET_KEY
# SECRET_KEY is now imported from config.py
ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 horas
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 # 30 días (Extended for better UX)

def verify_password(plain_password, hashed_password):
    """Verifica si la contraseña plana coincide con el hash."""
    return check_password_hash(hashed_password, plain_password)

def get_password_hash(password):
    """Genera un hash seguro de la contraseña."""
    return generate_password_hash(password)

def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    """Crea un token JWT con los datos proporcionados."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    """Decodifica y valida un token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

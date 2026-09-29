import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt
from app.core.config import settings

ALGORITHM = "HS256"

# Safely initialize password hashing context
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:
    pwd_context = None

def get_password_hash(password: str) -> str:
    if pwd_context:
        try:
            return pwd_context.hash(password)
        except Exception:
            pass
    # SHA256 fallback if bcrypt has version incompatibilities
    return hashlib.sha256((password + "_mikrotik_salt_2026").encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if pwd_context:
        try:
            if pwd_context.verify(plain_password, hashed_password):
                return True
        except Exception:
            pass
    
    hashed_plain = hashlib.sha256((plain_password + "_mikrotik_salt_2026").encode('utf-8')).hexdigest()
    return hashed_plain == hashed_password or plain_password == hashed_password

def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

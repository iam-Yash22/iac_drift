from datetime import datetime, timedelta

from jose import jwt

from app.core.config import settings


def create_access_token(data, expires_delta=None):
    """Create a signed JWT access token."""
    to_encode = dict(data)

    if expires_delta is not None:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.security.access_token_expire_minutes)

    to_encode.update({"exp": expire})

    secret_key = settings.security.secret_key.get_secret_value()
    algorithm = settings.security.algorithm

    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_token(token):
    """Decode and validate a signed JWT access token."""
    if not token:
        return None

    try:
        secret_key = settings.security.secret_key.get_secret_value()
        algorithm = settings.security.algorithm
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except Exception:
        return None

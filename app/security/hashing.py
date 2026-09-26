import hashlib
import hmac

from passlib.context import CryptContext

import app.core.config as config


pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(password):
    """Hash a plaintext password using Passlib's bcrypt-SHA256 scheme."""
    if password is None:
        raise ValueError("Password cannot be None")
    return pwd_context.hash(password)


def verify_password(password, hashed_password):
    """Verify a plaintext password against a bcrypt-SHA256 hash."""
    if not password or not hashed_password:
        return False
    try:
        return pwd_context.verify(password, hashed_password)
    except Exception:
        return False


def verify_hmac_signature(payload, signature, secret=None, digestmod=hashlib.sha256):
    """Verify an HMAC signature using constant-time comparison."""
    if signature is None:
        return False

    if secret is None:
        secret = getattr(config, "SECRET_KEY", None)
    if secret is None:
        secret = getattr(config, "HMAC_SECRET", None)
    if secret is None:
        secret = ""

    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        payload_bytes = payload if payload is not None else b""

    if isinstance(secret, str):
        secret_bytes = secret.encode("utf-8")
    else:
        secret_bytes = secret

    expected = hmac.new(secret_bytes, payload_bytes, digestmod).hexdigest()

    if isinstance(signature, str):
        return hmac.compare_digest(signature, expected)

    if isinstance(signature, (bytes, bytearray)):
        return hmac.compare_digest(signature, expected.encode("utf-8"))

    return False

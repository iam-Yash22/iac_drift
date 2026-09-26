from cryptography.fernet import Fernet

import app.core.config as config


def _get_fernet():
    """Build a Fernet instance from the configured key."""
    key = getattr(config, "FERNET_KEY", None)
    if not key:
        raise ValueError("FERNET_KEY is not configured")

    if isinstance(key, str):
        key = key.encode("utf-8")

    return Fernet(key)


def encrypt_value(value):
    """Encrypt a value using Fernet symmetric encryption."""
    if value is None:
        return None

    if isinstance(value, str):
        value = value.encode("utf-8")

    return _get_fernet().encrypt(value)


def decrypt_value(token):
    """Decrypt a Fernet-encrypted value."""
    if token is None:
        return None

    if isinstance(token, str):
        token = token.encode("utf-8")

    return _get_fernet().decrypt(token).decode("utf-8")

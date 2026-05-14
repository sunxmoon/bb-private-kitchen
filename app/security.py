import hashlib
import hmac
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode

import bcrypt

COOKIE_SECRET = None


def _load_or_create_secret(path: str) -> str:
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    secret = os.urandom(32).hex()
    with open(path, "w") as f:
        f.write(secret)
    os.chmod(path, 0o600)
    return secret


COOKIE_SECRET = os.getenv("COOKIE_SECRET") or _load_or_create_secret(".cookie_secret")


def is_production():
    return os.getenv("ENV", "").lower() == "production"


def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    )

def get_password_hash(password: str):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def sign_cookie_value(value: str) -> str:
    raw = value.encode()
    sig = hmac.new(COOKIE_SECRET.encode(), raw, hashlib.sha256).digest()
    sig_b64 = urlsafe_b64encode(sig).decode().rstrip("=")
    val_b64 = urlsafe_b64encode(raw).decode().rstrip("=")
    return sig_b64 + "." + val_b64


def verify_cookie_value(signed: str) -> str | None:
    try:
        sig_b64, val_b64 = signed.split(".", 1)
        def decode_b64(s: str):
            return urlsafe_b64decode(s + "=" * (4 - len(s) % 4))
        sig = decode_b64(sig_b64)
        val = decode_b64(val_b64)
        expected = hmac.new(COOKIE_SECRET.encode(), val, hashlib.sha256).digest()
        if hmac.compare_digest(sig, expected):
            return val.decode()
    except Exception:
        pass
    return None


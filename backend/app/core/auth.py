"""
Auth utilities:
  - JWT access tokens (Bearer)
  - OTP generation + HMAC-SHA256 verification
  - Token verify middleware helper
"""

import os
import hmac
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
OTP_SECRET = os.getenv("OTP_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

OTP_TTL_SECONDS = 300       # 5 минут
OTP_MAX_ATTEMPTS = 5


def create_access_token(user_id: int, extra: dict = None) -> str:
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_otp(user_id: int) -> tuple[str, str]:
    """
    Возвращает (otp_code, otp_hash).
    otp_hash хранится в Redis/DB, code отправляется пользователю.
    HMAC(OTP_SECRET, f"{user_id}:{code}:{timestamp_window}")
    """
    code = str(secrets.randbelow(900000) + 100000)  # 6 digits
    timestamp_window = int(time.time()) // OTP_TTL_SECONDS
    raw = f"{user_id}:{code}:{timestamp_window}"
    otp_hash = hmac.new(
        OTP_SECRET.encode(),
        raw.encode(),
        hashlib.sha256
    ).hexdigest()
    return code, otp_hash


def verify_otp(user_id: int, code: str, stored_hash: str, stored_at: datetime) -> bool:
    """
    Проверяет OTP код. Учитывает TTL и окно времени.
    """
    # TTL check
    elapsed = (datetime.now(timezone.utc) - stored_at.replace(tzinfo=timezone.utc)).total_seconds()
    if elapsed > OTP_TTL_SECONDS:
        return False

    # HMAC verify — текущее окно
    timestamp_window = int(time.time()) // OTP_TTL_SECONDS
    raw = f"{user_id}:{code}:{timestamp_window}"
    expected = hmac.new(
        OTP_SECRET.encode(),
        raw.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, stored_hash)


def generate_access_token_for_device(user_id: int, device_id: str) -> str:
    """Device-specific token с fingerprint."""
    return create_access_token(user_id, extra={"device": device_id})

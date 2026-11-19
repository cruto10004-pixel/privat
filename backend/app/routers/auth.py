"""
Auth endpoints:
  POST /auth/request  — запрос OTP (шлём через Telegram бот)
  POST /auth/verify   — верификация OTP → access token
  POST /auth/claim    — использование access code от админа
"""

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import generate_otp, verify_otp, create_access_token, OTP_MAX_ATTEMPTS
from app.models.user import User, OTPCode, AccessCode

logger = logging.getLogger("ayugram.auth")
router = APIRouter()

BOT_TOKEN = os.getenv("AUTH_BOT_TOKEN", "")
BOT_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ─── Schemas ─────────────────────────────────────────────────────────────────

class OTPRequestSchema(BaseModel):
    # Telegram ID или анонимный идентификатор
    identifier: str
    identifier_type: str = "telegram_id"  # "telegram_id" | "anon"


class OTPVerifySchema(BaseModel):
    identifier: str
    identifier_type: str = "telegram_id"
    code: str
    device_id: str


class AccessCodeClaimSchema(BaseModel):
    code: str
    username: str
    display_name: str = None
    device_id: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _send_otp_via_bot(telegram_id: int, code: str):
    """Отправляем OTP код через Telegram auth бот."""
    import httpx
    if not BOT_TOKEN:
        logger.warning("AUTH_BOT_TOKEN not set, skipping OTP send")
        return

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{BOT_API_URL}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": (
                        f"🔐 Ваш код авторизации AyuGram:\n\n"
                        f"<code>{code}</code>\n\n"
                        f"⏱ Действителен 5 минут.\n"
                        f"❌ Никому не сообщайте этот код."
                    ),
                    "parse_mode": "HTML",
                },
                timeout=10.0,
            )
        except Exception as e:
            logger.error(f"Failed to send OTP via bot: {e}")


async def _get_user_by_identifier(
    identifier: str,
    identifier_type: str,
    db: AsyncSession
) -> User | None:
    if identifier_type == "telegram_id":
        result = await db.execute(
            select(User).where(User.telegram_id == int(identifier))
        )
    else:
        result = await db.execute(
            select(User).where(User.anon_identifier == identifier)
        )
    return result.scalar_one_or_none()


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/request")
async def request_otp(data: OTPRequestSchema, db: AsyncSession = Depends(get_db)):
    """
    Запрашивает OTP. Если юзер найден — шлёт код через бот.
    Не раскрывает существование аккаунта (always 200).
    """
    user = await _get_user_by_identifier(data.identifier, data.identifier_type, db)
    if not user:
        # Не раскрываем — возвращаем 200
        return {"message": "If your account exists, a code has been sent"}

    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account banned")

    # Инвалидируем старые неиспользованные коды
    old_codes_result = await db.execute(
        select(OTPCode).where(
            OTPCode.user_id == user.id,
            OTPCode.is_used == False
        )
    )
    for old_code in old_codes_result.scalars().all():
        old_code.is_used = True

    # Генерируем новый
    code, code_hash = generate_otp(user.id)
    otp = OTPCode(user_id=user.id, code_hash=code_hash)
    db.add(otp)
    await db.flush()

    # Шлём
    if data.identifier_type == "telegram_id" and user.telegram_id:
        await _send_otp_via_bot(user.telegram_id, code)
    else:
        # Анонимный — логируем (в проде: другой канал доставки)
        logger.info(f"[ANON OTP] user_id={user.id} code={code}")

    return {"message": "If your account exists, a code has been sent"}


@router.post("/verify")
async def verify_otp_endpoint(data: OTPVerifySchema, db: AsyncSession = Depends(get_db)):
    """
    Верифицирует OTP. При успехе → JWT токен для девайса.
    """
    user = await _get_user_by_identifier(data.identifier, data.identifier_type, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Берём последний неиспользованный код
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.user_id == user.id,
            OTPCode.is_used == False
        ).order_by(OTPCode.created_at.desc()).limit(1)
    )
    otp = result.scalar_one_or_none()

    if not otp:
        raise HTTPException(status_code=401, detail="No active OTP")

    if otp.attempts >= OTP_MAX_ATTEMPTS:
        otp.is_used = True
        raise HTTPException(status_code=429, detail="Too many attempts")

    otp.attempts += 1

    if not verify_otp(user.id, data.code, otp.code_hash, otp.created_at):
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    otp.is_used = True

    # Регистрируем девайс или обновляем
    from app.models.user import Device
    dev_result = await db.execute(
        select(Device).where(
            Device.user_id == user.id,
            Device.device_id == data.device_id
        )
    )
    device = dev_result.scalar_one_or_none()

    token = create_access_token(user.id, extra={"device": data.device_id})

    if device:
        device.sync_token = token
        device.is_active = True
    else:
        device = Device(
            user_id=user.id,
            device_id=data.device_id,
            sync_token=token,
        )
        db.add(device)

    # Обновляем last seen
    user.last_seen_at = datetime.now(timezone.utc)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
    }


@router.post("/claim")
async def claim_access_code(data: AccessCodeClaimSchema, db: AsyncSession = Depends(get_db)):
    """
    Пользователь вводит invite code от администратора.
    Создаёт аккаунт + возвращает токен.
    """
    result = await db.execute(
        select(AccessCode).where(
            AccessCode.code == data.code,
            AccessCode.is_used == False
        )
    )
    access_code = result.scalar_one_or_none()

    if not access_code:
        raise HTTPException(status_code=404, detail="Invalid or used access code")

    # Проверяем уникальность username
    existing = await db.execute(
        select(User).where(User.username == data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    # Создаём пользователя
    user = User(
        username=data.username,
        display_name=data.display_name or data.username,
    )
    db.add(user)
    await db.flush()  # получаем user.id

    # Помечаем код использованным
    access_code.is_used = True
    access_code.assigned_to_user_id = user.id
    access_code.used_at = datetime.now(timezone.utc)

    # Создаём девайс
    from app.models.user import Device
    token = create_access_token(user.id, extra={"device": data.device_id})
    device = Device(
        user_id=user.id,
        device_id=data.device_id,
        sync_token=token,
    )
    db.add(device)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "message": "Account created successfully",
    }

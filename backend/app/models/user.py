"""
ORM модели:
  User       — основная запись пользователя
  Device     — зарегистрированные девайсы (AyuSync register)
  OTPCode    — одноразовые коды авторизации
  AccessCode — коды выдачи доступа (admin → user)
"""

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=True)
    
    # Telegram идентификатор — опциональный (для linkage)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=True, unique=True)
    # Анонимный идентификатор (специальный invite code)
    anon_identifier: Mapped[str] = mapped_column(String(64), nullable=True, unique=True)

    # Статусы
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ban_reason: Mapped[str] = mapped_column(Text, nullable=True)

    # Premium и внутренняя валюта
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    premium_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    stars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relations
    devices: Mapped[list["Device"]] = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    otp_codes: Mapped[list["OTPCode"]] = relationship("OTPCode", back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)  # из AyuSyncController
    device_name: Mapped[str] = mapped_column(String(256), nullable=True)
    
    # Токен для этого девайса (AyuSync token)
    sync_token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="devices")


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # HMAC-SHA256
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="otp_codes")


class AccessCode(Base):
    """
    Коды доступа, выдаваемые администратором.
    Пользователь вводит код → привязывается к аккаунту.
    """
    __tablename__ = "access_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    
    # Если уже привязан
    assigned_to_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_admin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

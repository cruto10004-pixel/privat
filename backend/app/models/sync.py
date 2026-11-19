"""
Sync модели:
  SyncMessage  — сохранённые/удалённые сообщения (AyuSyncBackend совместимость)
  Gift         — коллекционные подарки
  NFTItem      — NFT-совместимые объекты
"""

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SyncMessage(Base):
    """
    Синхронизируемые события сообщений.
    Совместимо с SyncEvent / SyncBatch из AyuGram клиента.
    """
    __tablename__ = "sync_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Telegram-специфичные поля (для hybrid mode)
    tg_message_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    tg_peer_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    
    # Тип события: "edited", "deleted", "read"
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    
    # Сериализованный payload (JSON из SyncEvent)
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Текст сообщения (для истории)
    message_text: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Медиа пути
    media_paths: Mapped[list] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class Gift(Base):
    """Коллекционные подарки."""
    __tablename__ = "gifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    gift_type: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "rare_star", "diamond"
    gift_name: Mapped[str] = mapped_column(String(128), nullable=False)
    gift_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)  # rarity, image_url, etc.
    
    # NFT-совместимые поля
    is_nft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nft_token_id: Mapped[str] = mapped_column(String(256), nullable=True, unique=True)
    
    is_transferable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    granted_by_admin_id: Mapped[int] = mapped_column(Integer, nullable=True)


class CollectibleUsername(Base):
    """Коллекционные username."""
    __tablename__ = "collectible_usernames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

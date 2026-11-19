"""
User endpoints — AyuSyncConfig.getUserDataURL():
  GET /user/v1          — данные текущего пользователя
  PATCH /user/v1        — обновление профиля
  GET /user/v1/history  — история сообщений
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.sync import SyncMessage, Gift, CollectibleUsername

router = APIRouter()


class UserUpdateSchema(BaseModel):
    display_name: str = None
    username: str = None


@router.get("/v1")
async def get_user_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AyuSyncConfig.getUserDataURL()
    Возвращает данные пользователя — то что AyuSyncController ожидает.
    """
    # Загружаем подарки
    gifts_result = await db.execute(
        select(Gift).where(Gift.owner_user_id == current_user.id)
    )
    gifts = gifts_result.scalars().all()

    # Коллекционные username
    usernames_result = await db.execute(
        select(CollectibleUsername).where(CollectibleUsername.owner_user_id == current_user.id)
    )
    collectibles = usernames_result.scalars().all()

    return {
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "telegram_id": current_user.telegram_id,
        "is_premium": current_user.is_premium,
        "premium_expires_at": (
            int(current_user.premium_expires_at.timestamp())
            if current_user.premium_expires_at else None
        ),
        "stars": current_user.stars,
        "created_at": int(current_user.created_at.timestamp()),
        "last_seen_at": (
            int(current_user.last_seen_at.timestamp())
            if current_user.last_seen_at else None
        ),
        "gifts": [
            {
                "id": g.id,
                "type": g.gift_type,
                "name": g.gift_name,
                "is_nft": g.is_nft,
                "nft_token_id": g.nft_token_id,
                "metadata": g.gift_metadata,
            }
            for g in gifts
        ],
        "collectible_usernames": [
            {
                "id": u.id,
                "username": u.username,
                "is_active": u.is_active,
            }
            for u in collectibles
        ],
    }


@router.patch("/v1")
async def update_user(
    data: UserUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.display_name is not None:
        current_user.display_name = data.display_name

    if data.username is not None:
        # Проверяем уникальность
        existing = await db.execute(
            select(User).where(
                User.username == data.username,
                User.id != current_user.id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username taken")
        current_user.username = data.username

    return {"updated": True, "username": current_user.username}


@router.get("/v1/history")
async def get_message_history(
    limit: int = 50,
    offset: int = 0,
    chat_id: int = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История сохранённых сообщений пользователя."""
    query = select(SyncMessage).where(
        SyncMessage.user_id == current_user.id
    )
    if chat_id:
        query = query.where(SyncMessage.tg_chat_id == chat_id)

    query = query.order_by(SyncMessage.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "event_type": m.event_type,
                "tg_message_id": m.tg_message_id,
                "tg_chat_id": m.tg_chat_id,
                "message_text": m.message_text,
                "payload": m.payload,
                "created_at": int(m.created_at.timestamp()),
            }
            for m in messages
        ],
        "total": len(messages),
        "offset": offset,
    }

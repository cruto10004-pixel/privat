"""
Sync endpoints — совместимы с AyuSyncConfig.java:
  POST /sync/register/v1  — регистрация девайса
  POST /sync/force/v1     — принудительная синхронизация
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, Device
from app.models.sync import SyncMessage

logger = logging.getLogger("ayugram.sync")
router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class RegisterDeviceSchema(BaseModel):
    device_id: str
    device_name: str = None


class ForceSyncSchema(BaseModel):
    # Список event ID которые клиент хочет синхронизировать
    event_ids: list[int] = []
    from_timestamp: int = 0  # unix timestamp


class SyncEventSchema(BaseModel):
    event_type: str              # "edited" | "deleted" | "read"
    tg_message_id: int = None
    tg_chat_id: int = None
    tg_peer_id: int = None
    message_text: str = None
    payload: dict = None


class SyncBatchSchema(BaseModel):
    events: list[SyncEventSchema]


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/register/v1")
async def register_device(
    data: RegisterDeviceSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AyuSyncConfig.getRegisterDeviceURL()
    Регистрирует девайс для текущего пользователя.
    """
    result = await db.execute(
        select(Device).where(
            Device.user_id == current_user.id,
            Device.device_id == data.device_id
        )
    )
    device = result.scalar_one_or_none()

    if device:
        device.device_name = data.device_name or device.device_name
        device.is_active = True
        device.last_sync_at = datetime.now(timezone.utc)
    else:
        from app.core.auth import create_access_token
        sync_token = create_access_token(
            current_user.id,
            extra={"device": data.device_id}
        )
        device = Device(
            user_id=current_user.id,
            device_id=data.device_id,
            device_name=data.device_name,
            sync_token=sync_token,
        )
        db.add(device)
        await db.flush()

    return {
        "device_id": device.device_id,
        "registered": True,
        "sync_token": device.sync_token,
        "user_id": current_user.id,
    }


@router.post("/force/v1")
async def force_sync(
    data: ForceSyncSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AyuSyncConfig.getForceSyncURL()
    Возвращает все события после from_timestamp.
    """
    from sqlalchemy import and_
    from datetime import datetime

    query = select(SyncMessage).where(
        SyncMessage.user_id == current_user.id,
    )

    if data.from_timestamp > 0:
        from_dt = datetime.fromtimestamp(data.from_timestamp, tz=timezone.utc)
        query = query.where(SyncMessage.created_at >= from_dt)

    if data.event_ids:
        query = query.where(SyncMessage.id.in_(data.event_ids))

    query = query.order_by(SyncMessage.created_at.asc()).limit(500)

    result = await db.execute(query)
    messages = result.scalars().all()

    return {
        "events": [
            {
                "id": m.id,
                "event_type": m.event_type,
                "tg_message_id": m.tg_message_id,
                "tg_chat_id": m.tg_chat_id,
                "tg_peer_id": m.tg_peer_id,
                "message_text": m.message_text,
                "payload": m.payload,
                "created_at": int(m.created_at.timestamp()),
            }
            for m in messages
        ],
        "count": len(messages),
    }


@router.post("/batch/v1")
async def push_sync_batch(
    batch: SyncBatchSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Принимает батч событий от клиента (AyuSyncController.pushBatch).
    """
    saved = []
    for event in batch.events:
        msg = SyncMessage(
            user_id=current_user.id,
            event_type=event.event_type,
            tg_message_id=event.tg_message_id,
            tg_chat_id=event.tg_chat_id,
            tg_peer_id=event.tg_peer_id,
            message_text=event.message_text,
            payload=event.payload,
        )
        db.add(msg)
        saved.append(msg)

    await db.flush()

    # Нотифицируем WebSocket клиентов этого пользователя
    from app.routers.ws import notify_user
    await notify_user(current_user.id, {
        "type": "sync_batch",
        "count": len(saved),
        "event_ids": [m.id for m in saved],
    })

    return {"saved": len(saved), "status": "ok"}

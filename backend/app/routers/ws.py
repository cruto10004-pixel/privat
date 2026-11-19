"""
WebSocket endpoint: /sync/ws/v1
Совместим с AyuSyncWebSocketClient.java

Протокол:
  client → server: {"type": "auth", "token": "<jwt>"}
  server → client: {"type": "auth_ok", "user_id": N}
  client → server: {"type": "ping"}
  server → client: {"type": "pong"}
  server → client: {"type": "sync_batch", "count": N, "event_ids": [...]}
  client → server: {"type": "event", "event_type": "...", ...}
"""

import asyncio
import json
import logging
from typing import dict as Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.auth import verify_token

logger = logging.getLogger("ayugram.ws")
router = APIRouter()

# connection pool: user_id → set of WebSocket connections
_connections: dict[int, set[WebSocket]] = {}
_lock = asyncio.Lock()


async def _register(user_id: int, ws: WebSocket):
    async with _lock:
        if user_id not in _connections:
            _connections[user_id] = set()
        _connections[user_id].add(ws)
        logger.info(f"WS connected: user_id={user_id}, total={len(_connections[user_id])}")


async def _unregister(user_id: int, ws: WebSocket):
    async with _lock:
        if user_id in _connections:
            _connections[user_id].discard(ws)
            if not _connections[user_id]:
                del _connections[user_id]
        logger.info(f"WS disconnected: user_id={user_id}")


async def notify_user(user_id: int, payload: dict):
    """Отправить сообщение всем WS соединениям пользователя."""
    async with _lock:
        connections = set(_connections.get(user_id, set()))

    if not connections:
        return

    message = json.dumps(payload)
    dead = set()
    for ws in connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)

    # Чистим мёртвые соединения
    if dead:
        async with _lock:
            if user_id in _connections:
                _connections[user_id] -= dead


@router.websocket("/sync/ws/v1")
async def websocket_sync(websocket: WebSocket):
    """
    AyuSyncConfig.getWebSocketURL() → wss://HOST/sync/ws/v1
    
    Аутентификация через первое сообщение:
    {"type": "auth", "token": "<jwt>"}
    
    AyuSyncWebSocketClient.java отправляет токен из AyuConfig.getSyncServerToken()
    """
    await websocket.accept()
    user_id: int | None = None

    try:
        # ── Handshake: ждём auth ──────────────────────────────────────
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)

        if msg.get("type") != "auth":
            await websocket.send_text(json.dumps({"type": "error", "message": "auth required"}))
            await websocket.close()
            return

        payload = verify_token(msg.get("token", ""))
        if not payload:
            await websocket.send_text(json.dumps({"type": "error", "message": "invalid token"}))
            await websocket.close()
            return

        user_id = int(payload["sub"])
        await _register(user_id, websocket)
        await websocket.send_text(json.dumps({"type": "auth_ok", "user_id": user_id}))

        # ── Main loop ─────────────────────────────────────────────────
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # keepalive ping
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "event":
                # Клиент пушит событие синхронизации
                await _handle_sync_event(user_id, msg, websocket)

            elif msg_type == "read_state":
                # Клиент сообщает о прочтении
                await websocket.send_text(json.dumps({
                    "type": "read_ack",
                    "chat_id": msg.get("chat_id"),
                }))

            else:
                logger.debug(f"Unknown WS message type: {msg_type}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error user_id={user_id}: {e}")
    finally:
        if user_id is not None:
            await _unregister(user_id, websocket)


async def _handle_sync_event(user_id: int, msg: dict, ws: WebSocket):
    """
    Обрабатывает SyncEvent от клиента.
    Сохраняет в БД и подтверждает.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.sync import SyncMessage

    event_type = msg.get("event_type", "unknown")
    async with AsyncSessionLocal() as db:
        sync_msg = SyncMessage(
            user_id=user_id,
            event_type=event_type,
            tg_message_id=msg.get("tg_message_id"),
            tg_chat_id=msg.get("tg_chat_id"),
            tg_peer_id=msg.get("tg_peer_id"),
            message_text=msg.get("message_text"),
            payload=msg.get("payload"),
        )
        db.add(sync_msg)
        await db.commit()
        await db.refresh(sync_msg)

    await ws.send_text(json.dumps({
        "type": "event_ack",
        "event_id": sync_msg.id,
        "event_type": event_type,
    }))

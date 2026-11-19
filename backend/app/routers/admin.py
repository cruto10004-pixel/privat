"""
Admin endpoints — управление пользователями, выдача premium, подарков, кодов доступа.
Все endpoints требуют is_admin=True.
"""

import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User, AccessCode
from app.models.sync import Gift, CollectibleUsername, SyncMessage

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CreateUserSchema(BaseModel):
    username: str
    display_name: str = None
    telegram_id: int = None
    anon_identifier: str = None


class BanUserSchema(BaseModel):
    user_id: int
    reason: str = None


class GrantPremiumSchema(BaseModel):
    user_id: int
    days: int = 30


class GrantStarsSchema(BaseModel):
    user_id: int
    amount: int


class GrantGiftSchema(BaseModel):
    user_id: int
    gift_type: str
    gift_name: str
    is_nft: bool = False
    nft_token_id: str = None
    metadata: dict = None


class GrantCollectibleUsernameSchema(BaseModel):
    user_id: int
    username: str


class GenerateAccessCodeSchema(BaseModel):
    count: int = 1  # сколько кодов сгенерировать


# ─── User management ─────────────────────────────────────────────────────────

@router.post("/users/create")
async def create_user(
    data: CreateUserSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт пользователя напрямую (без invite code)."""
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username taken")

    user = User(
        username=data.username,
        display_name=data.display_name or data.username,
        telegram_id=data.telegram_id,
        anon_identifier=data.anon_identifier,
    )
    db.add(user)
    await db.flush()

    return {"user_id": user.id, "username": user.username, "created": True}


@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Список всех пользователей."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    users = result.scalars().all()
    total = await db.execute(select(func.count(User.id)))

    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "telegram_id": u.telegram_id,
                "is_premium": u.is_premium,
                "stars": u.stars,
                "is_banned": u.is_banned,
                "is_admin": u.is_admin,
                "created_at": int(u.created_at.timestamp()),
                "last_seen_at": int(u.last_seen_at.timestamp()) if u.last_seen_at else None,
            }
            for u in users
        ],
        "total": total.scalar(),
        "offset": offset,
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "telegram_id": user.telegram_id,
        "anon_identifier": user.anon_identifier,
        "is_premium": user.is_premium,
        "premium_expires_at": str(user.premium_expires_at) if user.premium_expires_at else None,
        "stars": user.stars,
        "is_banned": user.is_banned,
        "ban_reason": user.ban_reason,
        "is_admin": user.is_admin,
        "created_at": str(user.created_at),
    }


@router.post("/users/ban")
async def ban_user(
    data: BanUserSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_banned = True
    user.ban_reason = data.reason
    return {"banned": True, "user_id": data.user_id}


@router.post("/users/unban")
async def unban_user(
    data: BanUserSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_banned = False
    user.ban_reason = None
    return {"unbanned": True, "user_id": data.user_id}


# ─── Premium & Stars ─────────────────────────────────────────────────────────

@router.post("/premium/grant")
async def grant_premium(
    data: GrantPremiumSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    if user.premium_expires_at and user.premium_expires_at > now:
        # Продлеваем
        user.premium_expires_at = user.premium_expires_at + timedelta(days=data.days)
    else:
        user.premium_expires_at = now + timedelta(days=data.days)

    user.is_premium = True
    return {
        "premium_granted": True,
        "user_id": data.user_id,
        "expires_at": str(user.premium_expires_at),
    }


@router.post("/premium/revoke")
async def revoke_premium(
    data: BanUserSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_premium = False
    user.premium_expires_at = None
    return {"premium_revoked": True, "user_id": data.user_id}


@router.post("/stars/grant")
async def grant_stars(
    data: GrantStarsSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.stars += data.amount
    return {"stars_granted": data.amount, "total_stars": user.stars, "user_id": data.user_id}


# ─── Gifts ───────────────────────────────────────────────────────────────────

@router.post("/gifts/grant")
async def grant_gift(
    data: GrantGiftSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    gift = Gift(
        owner_user_id=data.user_id,
        gift_type=data.gift_type,
        gift_name=data.gift_name,
        is_nft=data.is_nft,
        nft_token_id=data.nft_token_id or (secrets.token_hex(16) if data.is_nft else None),
        gift_metadata=data.metadata,
        granted_by_admin_id=admin.id,
    )
    db.add(gift)
    await db.flush()

    return {
        "gift_granted": True,
        "gift_id": gift.id,
        "user_id": data.user_id,
        "nft_token_id": gift.nft_token_id,
    }


@router.post("/usernames/grant")
async def grant_collectible_username(
    data: GrantCollectibleUsernameSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(CollectibleUsername).where(CollectibleUsername.username == data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already claimed")

    cu = CollectibleUsername(
        owner_user_id=data.user_id,
        username=data.username,
        is_active=False,
    )
    db.add(cu)
    await db.flush()
    return {"granted": True, "username": data.username, "user_id": data.user_id}


# ─── Access codes ─────────────────────────────────────────────────────────────

@router.post("/codes/generate")
async def generate_access_codes(
    data: GenerateAccessCodeSchema,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Генерирует invite codes для новых пользователей."""
    codes = []
    for _ in range(min(data.count, 50)):  # max 50 за раз
        code = secrets.token_urlsafe(12)
        ac = AccessCode(code=code)
        db.add(ac)
        codes.append(code)

    await db.flush()
    return {"codes": codes, "count": len(codes)}


@router.get("/codes")
async def list_access_codes(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AccessCode).order_by(AccessCode.created_at.desc()).limit(100)
    )
    codes = result.scalars().all()
    return {
        "codes": [
            {
                "code": c.code,
                "is_used": c.is_used,
                "assigned_to": c.assigned_to_user_id,
                "created_at": str(c.created_at),
                "used_at": str(c.used_at) if c.used_at else None,
            }
            for c in codes
        ]
    }


# ─── Stats ───────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users = await db.execute(select(func.count(User.id)))
    premium_users = await db.execute(
        select(func.count(User.id)).where(User.is_premium == True)
    )
    banned_users = await db.execute(
        select(func.count(User.id)).where(User.is_banned == True)
    )
    total_messages = await db.execute(select(func.count(SyncMessage.id)))
    total_gifts = await db.execute(select(func.count(Gift.id)))

    return {
        "users": {
            "total": total_users.scalar(),
            "premium": premium_users.scalar(),
            "banned": banned_users.scalar(),
        },
        "sync_messages": total_messages.scalar(),
        "gifts": total_gifts.scalar(),
    }

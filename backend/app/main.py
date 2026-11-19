"""
AyuGram Independent Backend
Совместим с AyuSyncConfig.java endpoints:
  POST /sync/register/v1
  WS   /sync/ws/v1
  GET  /user/v1
  POST /sync/force/v1
  GET  /ui/profile
  POST /auth/request
  POST /auth/verify
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.routers import auth, sync, user, admin, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ayugram")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    yield
    # shutdown
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title="AyuGram Backend",
    description="Independent messenger backend compatible with AyuGram Android client",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(ws.router, tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ayugram-backend"}


@app.get("/ui/profile")
async def profile_ui(token: str):
    """Страница профиля — AyuSyncConfig.getProfileURL()"""
    from app.core.auth import verify_token
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from sqlalchemy import select

    payload = verify_token(token)
    if not payload:
        return {"error": "invalid token"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.id == int(payload["sub"]))
        )
        user = result.scalar_one_or_none()
        if not user:
            return {"error": "user not found"}

    return {
        "username": user.username,
        "display_name": user.display_name,
        "premium": user.is_premium,
        "stars": user.stars,
        "created_at": str(user.created_at),
    }

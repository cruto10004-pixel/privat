"""
AyuGram Admin Bot
aiogram 3.x

Полная панель управления через Telegram.
Доступ только для Telegram ID из ADMIN_TELEGRAM_IDS.

Команды:
  /start          — главное меню
  /stats          — статистика
  /users [query]  — поиск/список пользователей
  /user <id>      — детали пользователя
  /ban <id>       — забанить
  /unban <id>     — разбанить
  /premium <id> <days> — выдать premium
  /stars <id> <amount> — выдать stars
  /gift <id>      — выдать подарок (FSM)
  /codes <N>      — сгенерировать N инвайт-кодов
  /backend        — проверить статус backend
"""

import asyncio
import logging
import os
from typing import Optional

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ayugram.admin_bot")

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
APP_NAME = os.getenv("APP_NAME", "AyuGram")

# Comma-separated список admin telegram IDs
_raw_admins = os.getenv("ADMIN_TELEGRAM_IDS", "")
ADMIN_IDS: set[int] = set(
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
)

# JWT токен суперадмина для запросов к backend API
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")

if not BOT_TOKEN:
    raise RuntimeError("ADMIN_BOT_TOKEN not set")

# ─── FSM States ───────────────────────────────────────────────────────────────

class GiftStates(StatesGroup):
    waiting_gift_type = State()
    waiting_gift_name = State()
    waiting_is_nft = State()
    confirm = State()

# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {ADMIN_API_TOKEN}"}


async def api_get(endpoint: str, params: dict = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{BACKEND_URL}{endpoint}",
                params=params,
                headers=_auth_headers(),
            )
            return resp.status_code, resp.json()
        except Exception as e:
            logger.error(f"API GET {endpoint}: {e}")
            return 503, {"detail": str(e)}


async def api_post(endpoint: str, payload: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{BACKEND_URL}{endpoint}",
                json=payload,
                headers=_auth_headers(),
            )
            return resp.status_code, resp.json()
        except Exception as e:
            logger.error(f"API POST {endpoint}: {e}")
            return 503, {"detail": str(e)}

# ─── Access guard ─────────────────────────────────────────────────────────────

def is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


def admin_only(handler):
    async def wrapper(message: Message, *args, **kwargs):
        if not is_admin(message):
            await message.answer("⛔ Доступ запрещён.")
            return
        return await handler(message, *args, **kwargs)
    return wrapper

# ─── Router ───────────────────────────────────────────────────────────────────

router = Router()

# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message):
        await message.answer("⛔ Нет доступа. Только для администраторов.")
        return

    await message.answer(
        f"🛠 <b>{APP_NAME} Admin Panel</b>\n\n"
        f"<b>Пользователи:</b>\n"
        f"/users — список\n"
        f"/user &lt;id&gt; — детали\n"
        f"/ban &lt;id&gt; [причина] — бан\n"
        f"/unban &lt;id&gt; — разбан\n\n"
        f"<b>Привилегии:</b>\n"
        f"/premium &lt;id&gt; &lt;days&gt; — выдать premium\n"
        f"/stars &lt;id&gt; &lt;amount&gt; — выдать stars\n"
        f"/gift &lt;id&gt; — выдать подарок\n\n"
        f"<b>Коды доступа:</b>\n"
        f"/codes [N] — сгенерировать N инвайт-кодов (default: 1)\n"
        f"/listcodes — список кодов\n\n"
        f"<b>Система:</b>\n"
        f"/stats — статистика\n"
        f"/backend — статус backend",
        parse_mode=ParseMode.HTML,
    )

# ── /stats ────────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message): return

    status, body = await api_get("/admin/stats")
    if status != 200:
        await message.answer(f"❌ Ошибка: {body.get('detail')}")
        return

    u = body["users"]
    await message.answer(
        f"📊 <b>Статистика {APP_NAME}</b>\n\n"
        f"👥 Пользователи: <b>{u['total']}</b>\n"
        f"⭐ Premium: <b>{u['premium']}</b>\n"
        f"🚫 Забанено: <b>{u['banned']}</b>\n\n"
        f"💬 Sync сообщений: <b>{body['sync_messages']}</b>\n"
        f"🎁 Подарков выдано: <b>{body['gifts']}</b>",
        parse_mode=ParseMode.HTML,
    )

# ── /backend ──────────────────────────────────────────────────────────────────

@router.message(Command("backend"))
async def cmd_backend(message: Message):
    if not is_admin(message): return

    status, body = await api_get("/health")
    if status == 200:
        await message.answer(f"✅ Backend онлайн: {body.get('service', 'ok')}")
    else:
        await message.answer(f"❌ Backend недоступен (HTTP {status})")

# ── /users ────────────────────────────────────────────────────────────────────

@router.message(Command("users"))
async def cmd_users(message: Message):
    if not is_admin(message): return

    status, body = await api_get("/admin/users", params={"limit": 20})
    if status != 200:
        await message.answer(f"❌ {body.get('detail')}")
        return

    users = body["users"]
    total = body["total"]

    if not users:
        await message.answer("Пользователей нет.")
        return

    lines = [f"👥 <b>Пользователи</b> (показано {len(users)}/{total}):\n"]
    for u in users:
        flags = []
        if u["is_premium"]: flags.append("⭐")
        if u["is_banned"]:  flags.append("🚫")
        if u["is_admin"]:   flags.append("🛠")
        flag_str = " ".join(flags)
        lines.append(
            f"<code>{u['id']}</code> @{u['username']} {flag_str}"
        )

    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

# ── /user <id> ────────────────────────────────────────────────────────────────

@router.message(Command("user"))
async def cmd_user(message: Message):
    if not is_admin(message): return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /user &lt;id&gt;", parse_mode=ParseMode.HTML)
        return

    user_id = int(args[1].strip())
    status, u = await api_get(f"/admin/users/{user_id}")

    if status == 404:
        await message.answer("❌ Пользователь не найден.")
        return
    if status != 200:
        await message.answer(f"❌ Ошибка: {u.get('detail')}")
        return

    premium_str = (
        f"✅ до {u['premium_expires_at']}" if u["is_premium"]
        else "❌ нет"
    )

    await message.answer(
        f"👤 <b>Пользователь #{u['id']}</b>\n\n"
        f"Username: <code>{u['username']}</code>\n"
        f"Имя: {u['display_name']}\n"
        f"Telegram ID: <code>{u.get('telegram_id', '—')}</code>\n"
        f"Анонимный ID: <code>{u.get('anon_identifier', '—')}</code>\n\n"
        f"⭐ Premium: {premium_str}\n"
        f"🌟 Stars: <b>{u['stars']}</b>\n"
        f"🛠 Админ: {'да' if u['is_admin'] else 'нет'}\n"
        f"🚫 Бан: {'да — ' + (u['ban_reason'] or '') if u['is_banned'] else 'нет'}\n\n"
        f"📅 Создан: {u['created_at']}",
        parse_mode=ParseMode.HTML,
    )

# ── /ban <id> [reason] ────────────────────────────────────────────────────────

@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message): return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: /ban &lt;id&gt; [причина]", parse_mode=ParseMode.HTML)
        return

    user_id = int(parts[1])
    reason = parts[2] if len(parts) > 2 else None

    status, body = await api_post("/admin/users/ban", {"user_id": user_id, "reason": reason})
    if status == 200:
        await message.answer(f"🚫 Пользователь #{user_id} заблокирован.")
    elif status == 404:
        await message.answer("❌ Пользователь не найден.")
    else:
        await message.answer(f"❌ Ошибка: {body.get('detail')}")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message): return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: /unban &lt;id&gt;", parse_mode=ParseMode.HTML)
        return

    user_id = int(parts[1])
    status, body = await api_post("/admin/users/unban", {"user_id": user_id})
    if status == 200:
        await message.answer(f"✅ Пользователь #{user_id} разблокирован.")
    elif status == 404:
        await message.answer("❌ Пользователь не найден.")
    else:
        await message.answer(f"❌ Ошибка: {body.get('detail')}")

# ── /premium <id> <days> ──────────────────────────────────────────────────────

@router.message(Command("premium"))
async def cmd_premium(message: Message):
    if not is_admin(message): return

    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer(
            "Использование: /premium &lt;user_id&gt; &lt;days&gt;\n"
            "Пример: /premium 42 30",
            parse_mode=ParseMode.HTML,
        )
        return

    user_id = int(parts[1])
    days = int(parts[2])

    status, body = await api_post("/admin/premium/grant", {"user_id": user_id, "days": days})
    if status == 200:
        await message.answer(
            f"⭐ Premium выдан пользователю #{user_id} на {days} дней.\n"
            f"Истекает: {body.get('expires_at', '?')}"
        )
    elif status == 404:
        await message.answer("❌ Пользователь не найден.")
    else:
        await message.answer(f"❌ {body.get('detail')}")

# ── /stars <id> <amount> ──────────────────────────────────────────────────────

@router.message(Command("stars"))
async def cmd_stars(message: Message):
    if not is_admin(message): return

    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer(
            "Использование: /stars &lt;user_id&gt; &lt;amount&gt;\n"
            "Пример: /stars 42 500",
            parse_mode=ParseMode.HTML,
        )
        return

    user_id = int(parts[1])
    amount = int(parts[2])

    status, body = await api_post("/admin/stars/grant", {"user_id": user_id, "amount": amount})
    if status == 200:
        await message.answer(
            f"🌟 Выдано {amount} stars пользователю #{user_id}.\n"
            f"Всего stars: {body.get('total_stars', '?')}"
        )
    elif status == 404:
        await message.answer("❌ Пользователь не найден.")
    else:
        await message.answer(f"❌ {body.get('detail')}")

# ── /gift <user_id> — FSM ─────────────────────────────────────────────────────

@router.message(Command("gift"))
async def cmd_gift_start(message: Message, state: FSMContext):
    if not is_admin(message): return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: /gift &lt;user_id&gt;", parse_mode=ParseMode.HTML)
        return

    user_id = int(parts[1])
    await state.update_data(target_user_id=user_id)

    await message.answer(
        f"🎁 Выдача подарка пользователю #{user_id}\n\n"
        f"Введи тип подарка (например: <code>rare_star</code>, <code>diamond</code>, <code>crown</code>):",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(GiftStates.waiting_gift_type)


@router.message(GiftStates.waiting_gift_type)
async def gift_type(message: Message, state: FSMContext):
    gift_type = message.text.strip().lower().replace(" ", "_")
    await state.update_data(gift_type=gift_type)
    await message.answer(
        f"Тип: <code>{gift_type}</code>\n\n"
        f"Теперь введи отображаемое название подарка:",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(GiftStates.waiting_gift_name)


@router.message(GiftStates.waiting_gift_name)
async def gift_name(message: Message, state: FSMContext):
    gift_name = message.text.strip()
    await state.update_data(gift_name=gift_name)
    await message.answer(
        f"Название: <b>{gift_name}</b>\n\n"
        f"Сделать NFT-совместимым? Введи <code>да</code> или <code>нет</code>:",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(GiftStates.waiting_is_nft)


@router.message(GiftStates.waiting_is_nft)
async def gift_nft(message: Message, state: FSMContext):
    is_nft = message.text.strip().lower() in ("да", "yes", "1", "true")
    await state.update_data(is_nft=is_nft)
    data = await state.get_data()

    await message.answer(
        f"📋 <b>Подтверждение:</b>\n\n"
        f"Пользователь: #{data['target_user_id']}\n"
        f"Тип: <code>{data['gift_type']}</code>\n"
        f"Название: {data['gift_name']}\n"
        f"NFT: {'✅ да' if is_nft else '❌ нет'}\n\n"
        f"Подтвердить? /confirm или /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(GiftStates.confirm)


@router.message(GiftStates.confirm, Command("confirm"))
async def gift_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    status, body = await api_post("/admin/gifts/grant", {
        "user_id": data["target_user_id"],
        "gift_type": data["gift_type"],
        "gift_name": data["gift_name"],
        "is_nft": data.get("is_nft", False),
    })

    if status == 200:
        nft_str = f"\nNFT token: <code>{body.get('nft_token_id')}</code>" if data.get("is_nft") else ""
        await message.answer(
            f"🎁 Подарок выдан!\n"
            f"Gift ID: <code>{body.get('gift_id')}</code>{nft_str}",
            parse_mode=ParseMode.HTML,
        )
    elif status == 404:
        await message.answer("❌ Пользователь не найден.")
    else:
        await message.answer(f"❌ {body.get('detail')}")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Отменено.", reply_markup=ReplyKeyboardRemove())

# ── /codes [N] ────────────────────────────────────────────────────────────────

@router.message(Command("codes"))
async def cmd_codes(message: Message):
    if not is_admin(message): return

    parts = message.text.split()
    count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    count = min(count, 50)

    status, body = await api_post("/admin/codes/generate", {"count": count})
    if status != 200:
        await message.answer(f"❌ {body.get('detail')}")
        return

    codes = body["codes"]
    code_lines = "\n".join(f"<code>{c}</code>" for c in codes)
    await message.answer(
        f"🔑 Сгенерировано {len(codes)} инвайт-код(ов):\n\n{code_lines}\n\n"
        f"Передай их пользователям через /code в @{(await _get_auth_bot_username())}",
        parse_mode=ParseMode.HTML,
    )


async def _get_auth_bot_username() -> str:
    auth_bot_name = os.getenv("AUTH_BOT_USERNAME", "ayugram_auth_bot")
    return auth_bot_name


@router.message(Command("listcodes"))
async def cmd_listcodes(message: Message):
    if not is_admin(message): return

    status, body = await api_get("/admin/codes")
    if status != 200:
        await message.answer(f"❌ {body.get('detail')}")
        return

    codes = body["codes"]
    if not codes:
        await message.answer("Кодов нет.")
        return

    lines = ["📋 <b>Коды доступа:</b>\n"]
    for c in codes[:30]:  # показываем первые 30
        status_str = "✅ использован" if c["is_used"] else "⏳ свободен"
        lines.append(f"<code>{c['code']}</code> — {status_str}")

    if len(codes) > 30:
        lines.append(f"\n...и ещё {len(codes) - 30}")

    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

# ── Fallback ──────────────────────────────────────────────────────────────────

@router.message()
async def fallback(message: Message, state: FSMContext):
    if not is_admin(message):
        await message.answer("⛔ Доступ запрещён.")
        return

    current = await state.get_state()
    if current:
        await message.answer("Введи запрошенное значение или /cancel")
    else:
        await message.answer("Используй /start для списка команд.")

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info(f"Starting {APP_NAME} Admin Bot...")
    logger.info(f"Authorized admins: {ADMIN_IDS}")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())

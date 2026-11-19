"""
AyuGram Authorization Bot
aiogram 3.x

Функции:
  /start              — приветствие, показ идентификатора
  /login              — запрос OTP для входа в приложение
  /code <XXXX-XXXX>   — использование invite code от администратора
  /cancel             — отмена текущего действия

Схема работы:
  1. Пользователь пишет /login
  2. Бот запрашивает у backend POST /auth/request (identifier = telegram_id)
  3. Backend генерирует OTP и вызывает _send_otp_via_bot()
  4. Бот доставляет код пользователю
  5. Пользователь вводит код в AyuGram клиенте
  6. Клиент POST /auth/verify → получает JWT

Invite code flow:
  1. Пользователь пишет /code INVITE_CODE
  2. Бот вызывает POST /auth/claim
  3. Бот просит ввести username
  4. Аккаунт создаётся, бот возвращает токен (для ручного ввода в настройках)
"""

import asyncio
import logging
import os
import httpx

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ayugram.auth_bot")

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("AUTH_BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
# Имя приложения для отображения
APP_NAME = os.getenv("APP_NAME", "AyuGram")

if not BOT_TOKEN:
    raise RuntimeError("AUTH_BOT_TOKEN not set")

# ─── FSM States ───────────────────────────────────────────────────────────────

class ClaimStates(StatesGroup):
    waiting_username = State()
    waiting_display_name = State()
    confirm = State()

class LoginStates(StatesGroup):
    waiting_confirm = State()

# ─── HTTP client helper ───────────────────────────────────────────────────────

async def backend_post(endpoint: str, payload: dict) -> tuple[int, dict]:
    """POST к backend. Возвращает (status_code, json_body)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{BACKEND_URL}{endpoint}", json=payload)
            return resp.status_code, resp.json()
        except Exception as e:
            logger.error(f"Backend POST {endpoint} failed: {e}")
            return 503, {"detail": "Backend unavailable"}

async def backend_get(endpoint: str, params: dict = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BACKEND_URL}{endpoint}", params=params)
            return resp.status_code, resp.json()
        except Exception as e:
            logger.error(f"Backend GET {endpoint} failed: {e}")
            return 503, {"detail": "Backend unavailable"}

# ─── Router ───────────────────────────────────────────────────────────────────

router = Router()

# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    username = message.from_user.username or "—"

    await message.answer(
        f"👋 Привет! Это официальный бот авторизации <b>{APP_NAME}</b>.\n\n"
        f"🆔 Твой Telegram ID: <code>{tg_id}</code>\n"
        f"👤 Username: @{username}\n\n"
        f"<b>Доступные команды:</b>\n"
        f"/login — запросить код для входа в приложение\n"
        f"/code — использовать инвайт-код от администратора\n\n"
        f"Если у тебя нет аккаунта — обратись к администратору за инвайт-кодом.",
        parse_mode=ParseMode.HTML,
    )

# ── /login ────────────────────────────────────────────────────────────────────

@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id

    # Запрашиваем OTP у backend
    status, body = await backend_post("/auth/request", {
        "identifier": str(tg_id),
        "identifier_type": "telegram_id",
    })

    if status == 503:
        await message.answer(
            "⚠️ Сервер временно недоступен. Попробуй позже.",
        )
        return

    # Backend всегда 200 (не раскрывает существование аккаунта)
    await message.answer(
        "📨 Если твой аккаунт существует — код уже отправлен.\n\n"
        "🔢 Введи его в приложении <b>AyuGram</b> в поле авторизации.\n\n"
        "⏱ Код действителен <b>5 минут</b>.\n"
        "❓ Нет аккаунта? Используй /code для инвайта.",
        parse_mode=ParseMode.HTML,
    )

# ── OTP delivery (вызывается из backend через этот же бот) ────────────────────

@router.message(Command("otp"))
async def cmd_otp_internal(message: Message):
    """
    Этот handler НЕ для пользователей.
    Backend вызывает Telegram Bot API напрямую через sendMessage.
    Команда /otp здесь для теста в dev режиме.
    """
    if os.getenv("DEBUG", "false").lower() != "true":
        return
    await message.answer("Debug: OTP endpoint active")

# ── /code <INVITE_CODE> ───────────────────────────────────────────────────────

@router.message(Command("code"))
async def cmd_code(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split(maxsplit=1)

    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "✉️ Укажи инвайт-код:\n"
            "<code>/code ВАШ_КОД</code>\n\n"
            "Пример: <code>/code AbCdEfGh1234</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    invite_code = args[1].strip()
    await state.update_data(invite_code=invite_code)

    await message.answer(
        f"✅ Код принят: <code>{invite_code}</code>\n\n"
        f"👤 Введи желаемый <b>username</b> для аккаунта\n"
        f"(только латиница, цифры, подчёркивание, 3–32 символа):",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(ClaimStates.waiting_username)


@router.message(ClaimStates.waiting_username)
async def process_username(message: Message, state: FSMContext):
    username = message.text.strip()

    # Валидация
    if not username.replace("_", "").isalnum() or not (3 <= len(username) <= 32):
        await message.answer(
            "❌ Невалидный username.\n"
            "Только латиница, цифры и _, от 3 до 32 символов.\n"
            "Попробуй ещё раз:",
        )
        return

    await state.update_data(username=username)
    await message.answer(
        f"👋 Теперь введи отображаемое имя (можно на любом языке):\n"
        f"Или отправь /skip чтобы использовать username как имя.",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(ClaimStates.waiting_display_name)


@router.message(ClaimStates.waiting_display_name, Command("skip"))
async def skip_display_name(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(display_name=data["username"])
    await _do_claim(message, state)


@router.message(ClaimStates.waiting_display_name)
async def process_display_name(message: Message, state: FSMContext):
    display_name = message.text.strip()
    if len(display_name) > 128:
        await message.answer("❌ Имя слишком длинное (макс 128 символов).")
        return

    await state.update_data(display_name=display_name)
    await _do_claim(message, state)


async def _do_claim(message: Message, state: FSMContext):
    data = await state.get_data()
    tg_id = message.from_user.id

    await message.answer("⏳ Создаём аккаунт...")

    status, body = await backend_post("/auth/claim", {
        "code": data["invite_code"],
        "username": data["username"],
        "display_name": data.get("display_name", data["username"]),
        "device_id": f"tgbot_{tg_id}",
    })

    await state.clear()

    if status == 200:
        token = body.get("access_token", "")
        user_id = body.get("user_id")
        await message.answer(
            f"🎉 <b>Аккаунт создан!</b>\n\n"
            f"👤 Username: <code>{body.get('username')}</code>\n"
            f"🆔 User ID: <code>{user_id}</code>\n\n"
            f"🔑 <b>Твой токен для AyuGram:</b>\n"
            f"<code>{token}</code>\n\n"
            f"📱 Вставь его в настройках приложения:\n"
            f"<i>Настройки → AyuGram → Sync Server → Token</i>\n\n"
            f"⚠️ Не показывай токен никому!",
            parse_mode=ParseMode.HTML,
        )
    elif status == 404:
        await message.answer(
            "❌ Инвайт-код недействителен или уже использован.\n"
            "Обратись к администратору за новым кодом.",
        )
    elif status == 409:
        await message.answer(
            f"❌ Username <code>{data['username']}</code> уже занят.\n"
            f"Попробуй /code снова с другим username.",
            parse_mode=ParseMode.HTML,
        )
    elif status == 503:
        await message.answer("⚠️ Сервер недоступен. Попробуй позже.")
    else:
        await message.answer(
            f"❌ Ошибка: {body.get('detail', 'Unknown error')} (код {status})"
        )

# ── /cancel ───────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer(
            "✅ Действие отменено.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer("Нечего отменять.")

# ── /help ─────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        f"<b>{APP_NAME} Auth Bot — помощь</b>\n\n"
        f"/start — информация о боте\n"
        f"/login — получить OTP для входа (если аккаунт уже есть)\n"
        f"/code XXXX — создать аккаунт по инвайт-коду\n"
        f"/cancel — отменить текущее действие\n\n"
        f"<b>Нет аккаунта?</b> Обратись к администратору проекта за инвайт-кодом.",
        parse_mode=ParseMode.HTML,
    )

# ── Fallback ──────────────────────────────────────────────────────────────────

@router.message()
async def fallback(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        # Пользователь в каком-то state — подсказываем
        await message.answer(
            "Введи запрошенное значение или используй /cancel для отмены."
        )
    else:
        await message.answer(
            "Используй /help для списка команд."
        )

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info(f"Starting {APP_NAME} Auth Bot...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())

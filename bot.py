"""
Лидген-бот: приём заявок на разработку Telegram-ботов.

Меню: калькулятор примерной стоимости, форма заявки (тип бота, описание,
контакт) и отзывы с ручной модерацией. Все данные — в SQLite (db.py).

Запуск:
    export BOT_TOKEN="токен_от_BotFather"
    python bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import db
from config import ADMIN_ID, BOT_TOKEN, BOT_TYPES, HOSTING_NOTE, PRICING, TIER_LABELS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp = Dispatcher(storage=MemoryStorage())


WELCOME_TEXT = (
    "Привет! Я делаю Telegram-ботов на заказ — быстро и недорого. "
    "Что вас интересует?"
)

BTN_REQUEST = "📝 Оставить заявку"
BTN_PRICE = "💰 Узнать примерную стоимость"
BTN_REVIEWS = "⭐ Отзывы"
BTN_CANCEL = "✖️ Отмена"
BTN_SHARE_CONTACT = "📱 Поделиться контактом"
BTN_LEAVE_REVIEW = "✍️ Оставить отзыв"
BTN_SEND = "✅ Отправить"
BTN_SEND_ANON = "🙈 Отправить анонимно"
BTN_OTHER_TYPE = "Другое"

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_REQUEST)],
        [KeyboardButton(text=BTN_PRICE)],
        [KeyboardButton(text=BTN_REVIEWS)],
    ],
    resize_keyboard=True,
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
    resize_keyboard=True,
)

contact_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_SHARE_CONTACT, request_contact=True)],
        [KeyboardButton(text=BTN_CANCEL)],
    ],
    resize_keyboard=True,
)


def calc_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name.capitalize(), callback_data=f"calc:{key}")]
            for key, name in BOT_TYPES.items()
        ]
    )


def request_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name.capitalize(), callback_data=f"reqtype:{key}")]
            for key, name in BOT_TYPES.items()
        ]
        + [[InlineKeyboardButton(text=BTN_OTHER_TYPE, callback_data="reqtype:other")]]
    )


class RequestForm(StatesGroup):
    choosing_type = State()
    entering_custom_type = State()
    entering_description = State()
    entering_contact = State()


class ReviewForm(StatesGroup):
    entering_text = State()


# ---------- старт и отмена ----------

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_kb)


@dp.message(F.text == BTN_CANCEL)
async def cancel_any(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено. Чем ещё могу помочь?", reply_markup=main_kb)


# ---------- калькулятор стоимости ----------

@dp.message(F.text == BTN_PRICE)
async def price_start(message: Message) -> None:
    await message.answer("Выберите тип бота:", reply_markup=calc_type_kb())


def _support_block() -> str:
    lines = [f"{TIER_LABELS[key]}: {info['support']}" for key, info in PRICING.items()]
    return (
        "Также доступно ежемесячное сопровождение бота (доработки, "
        "исправление багов, мелкие правки):\n\n" + "\n".join(lines)
    )


@dp.callback_query(F.data.startswith("calc:"))
async def price_show(callback: CallbackQuery) -> None:
    key = callback.data.split(":", 1)[1]
    info = PRICING[key]
    text = (
        f"{BOT_TYPES[key].capitalize()}\n\n"
        f"Цена: {info['price']}\n"
        f"Срок: {info['eta']}\n\n"
        f"{_support_block()}\n\n"
        f"{HOSTING_NOTE}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BTN_REQUEST, callback_data=f"req:start:{key}")]]
    )
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=kb)


# ---------- заявка ----------

@dp.message(F.text == BTN_REQUEST)
async def request_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RequestForm.choosing_type)
    await message.answer("Какой тип бота вам нужен?", reply_markup=request_type_kb())


@dp.callback_query(F.data.startswith("req:start:"))
async def request_start_prefilled(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 2)[2]
    await state.clear()
    await state.update_data(bot_type=BOT_TYPES.get(key, key))
    await state.set_state(RequestForm.entering_description)
    await callback.answer()
    await callback.message.answer(
        "Опишите вашу задачу свободным текстом — что должен делать бот.",
        reply_markup=cancel_kb,
    )


@dp.callback_query(RequestForm.choosing_type, F.data.startswith("reqtype:"))
async def request_type_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    await callback.answer()
    if key == "other":
        await state.set_state(RequestForm.entering_custom_type)
        await callback.message.answer(
            "Опишите в двух словах, какой тип бота вам нужен.",
            reply_markup=cancel_kb,
        )
        return

    await state.update_data(bot_type=BOT_TYPES[key])
    await state.set_state(RequestForm.entering_description)
    await callback.message.answer(
        "Опишите вашу задачу свободным текстом — что должен делать бот.",
        reply_markup=cancel_kb,
    )


@dp.message(RequestForm.entering_custom_type, F.text)
async def request_custom_type(message: Message, state: FSMContext) -> None:
    await state.update_data(bot_type=message.text.strip())
    await state.set_state(RequestForm.entering_description)
    await message.answer(
        "Опишите вашу задачу свободным текстом — что должен делать бот.",
        reply_markup=cancel_kb,
    )


@dp.message(RequestForm.entering_description, F.text)
async def request_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(RequestForm.entering_contact)
    await message.answer(
        "Оставьте контакт для связи: поделитесь номером телефона кнопкой ниже "
        "или напишите вручную (телефон, @username и т.п.).",
        reply_markup=contact_kb,
    )


@dp.message(RequestForm.entering_contact, F.contact)
async def request_contact_shared(message: Message, state: FSMContext, bot: Bot) -> None:
    await _finish_request(message, state, bot, message.contact.phone_number)


@dp.message(RequestForm.entering_contact, F.text)
async def request_contact_typed(message: Message, state: FSMContext, bot: Bot) -> None:
    await _finish_request(message, state, bot, message.text.strip())


async def _finish_request(message: Message, state: FSMContext, bot: Bot, contact: str) -> None:
    data = await state.get_data()
    await state.clear()

    user = message.from_user
    bot_type = data.get("bot_type", "не указан")
    description = data.get("description", "")

    request_id = db.add_request(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        bot_type=bot_type,
        description=description,
        contact=contact,
    )

    await message.answer("Спасибо! Свяжусь с вами в течение дня.", reply_markup=main_kb)
    await _notify_admin_request(bot, request_id, user, bot_type, description, contact)


async def _notify_admin_request(bot: Bot, request_id: int, user, bot_type: str, description: str, contact: str) -> None:
    if not ADMIN_ID:
        return
    username_line = f"@{user.username}" if user.username else "нет username"
    text = (
        f"🆕 Новая заявка #{request_id}\n\n"
        f"От: {user.full_name} ({username_line}, id {user.id})\n"
        f"Тип бота: {bot_type}\n"
        f"Описание: {description}\n"
        f"Контакт: {contact}"
    )
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logger.exception("Failed to notify admin about new request")


# ---------- отзывы ----------

@dp.message(F.text == BTN_REVIEWS)
async def reviews_list(message: Message) -> None:
    reviews = db.get_approved_reviews()
    if not reviews:
        text = "Пока нет отзывов, но уже работаю над первыми проектами!"
    else:
        lines = []
        for r in reviews:
            if r["is_anonymous"]:
                author = "Аноним"
            elif r["username"]:
                author = f"{r['full_name']} (@{r['username']})"
            else:
                author = r["full_name"]
            lines.append(f"{author}: {r['text']}")
        text = "\n\n".join(lines)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BTN_LEAVE_REVIEW, callback_data="review:start")]]
    )
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "review:start")
async def review_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ReviewForm.entering_text)
    await callback.answer()
    await callback.message.answer("Напишите текст отзыва одним сообщением.", reply_markup=cancel_kb)


@dp.message(ReviewForm.entering_text, F.text)
async def review_text_entered(message: Message, state: FSMContext) -> None:
    await state.update_data(review_text=message.text.strip())
    user = message.from_user
    author = f"{user.full_name} (@{user.username})" if user.username else user.full_name
    preview = f"Так будет выглядеть ваш отзыв:\n{author}: {message.text.strip()}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SEND, callback_data="review:send")],
            [InlineKeyboardButton(text=BTN_SEND_ANON, callback_data="review:send_anon")],
        ]
    )
    await message.answer(preview, reply_markup=kb)


@dp.callback_query(ReviewForm.entering_text, F.data.in_({"review:send", "review:send_anon"}))
async def review_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text = data.get("review_text", "")
    await state.clear()

    is_anonymous = callback.data == "review:send_anon"
    user = callback.from_user
    review_id = db.add_review(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        text=text,
        is_anonymous=is_anonymous,
    )

    await callback.answer()
    await callback.message.edit_text("Спасибо! Отзыв отправлен на модерацию.")
    await callback.message.answer("Чем ещё могу помочь?", reply_markup=main_kb)
    await _notify_admin_review(bot, review_id, user, text, is_anonymous)


async def _notify_admin_review(bot: Bot, review_id: int, user, text: str, is_anonymous: bool) -> None:
    if not ADMIN_ID:
        return
    username_line = f"@{user.username}" if user.username else "нет username"
    anon_line = "да" if is_anonymous else "нет"
    text = (
        f"🆕 Новый отзыв #{review_id} (анонимно для публикации: {anon_line})\n\n"
        f"Реальный автор: {user.full_name} ({username_line}, id {user.id})\n\n"
        f"Текст: {text}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"review:approve:{review_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"review:reject:{review_id}"),
        ]]
    )
    try:
        sent = await bot.send_message(ADMIN_ID, text, reply_markup=kb)
        db.set_review_admin_message_id(review_id, sent.message_id)
    except Exception:
        logger.exception("Failed to notify admin about new review")


@dp.callback_query(F.data.startswith("review:approve:"))
async def review_approve(callback: CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Только админ может это делать", show_alert=True)
        return

    review_id = int(callback.data.split(":", 2)[2])
    review = db.get_review(review_id)
    if not review or review["status"] != "pending":
        await callback.answer("Уже обработано", show_alert=True)
        return

    db.set_review_status(review_id, "approved")
    await callback.answer("Одобрено")
    try:
        await callback.message.edit_text(callback.message.text + "\n\n✅ ОДОБРЕНО")
    except Exception:
        pass


@dp.callback_query(F.data.startswith("review:reject:"))
async def review_reject(callback: CallbackQuery) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Только админ может это делать", show_alert=True)
        return

    review_id = int(callback.data.split(":", 2)[2])
    review = db.get_review(review_id)
    if not review or review["status"] != "pending":
        await callback.answer("Уже обработано", show_alert=True)
        return

    db.set_review_status(review_id, "rejected")
    await callback.answer("Отклонено")
    try:
        await callback.message.edit_text(callback.message.text + "\n\n❌ ОТКЛОНЕНО")
    except Exception:
        pass


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Сделай: export BOT_TOKEN='твой_токен_от_BotFather'")

    db.init_db()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = "ТВОЙ_ТОКЕН"
ADMIN_ID = 7799445685

bot = Bot(TOKEN)
dp = Dispatcher()

# ================= БАЗА =================

db = sqlite3.connect("users.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    pro_until TEXT,
    active INTEGER DEFAULT 1
)
""")
db.commit()

# ================= КЛАВИАТУРА =================

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Аренда"), KeyboardButton(text="🏡 Продажа")],
        [KeyboardButton(text="🎁 Бесплатно 2 часа")],
        [KeyboardButton(text="💳 Я оплатил")]
    ],
    resize_keyboard=True
)

# ================= ПАРСЕР (заглушка) =================

async def parse(url):
    return [
        "🏠 Объявление 1",
        "🏠 Объявление 2",
        "🏠 Объявление 3"
    ]

async def send_results(user_id, url):
    ads = await parse(url)
    for ad in ads:
        await bot.send_message(user_id, ad)

# ================= ПРОВЕРКА ДОСТУПА =================

async def has_access(user_id):
    cursor.execute("SELECT pro_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        return False

    expire = datetime.fromisoformat(row[0])
    return expire > datetime.now()

# ================= START =================

@dp.message(Command("start"))
async def start(message: types.Message):

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, active) VALUES (?, 1)",
        (message.from_user.id,)
    )
    db.commit()

    await message.answer("👋 Добро пожаловать!\nВыберите действие:", reply_markup=keyboard)

# ================= ОБЩИЙ HANDLER =================

@dp.message()
async def handler(message: types.Message):

    user_id = message.from_user.id

    # создаём пользователя если нет
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, active) VALUES (?, 1)",
        (user_id,)
    )
    db.commit()

    # 🎁 Бесплатно
    if message.text == "🎁 Бесплатно 2 часа":
        expire = datetime.now() + timedelta(hours=2)

        cursor.execute(
            "UPDATE users SET pro_until=? WHERE user_id=?",
            (expire.isoformat(), user_id)
        )
        db.commit()

        await message.answer(f"✅ Доступ до {expire.strftime('%H:%M %d.%m.%Y')}")
        return

    # 💳 Оплата
    if message.text == "💳 Я оплатил":

        keyboard_admin = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"approve_{user_id}"
                )]
            ]
        )

        await bot.send_message(
            ADMIN_ID,
            f"💰 Новый платёж\nID: {user_id}",
            reply_markup=keyboard_admin
        )

        await message.answer("⏳ Ожидайте подтверждения")
        return

    # 🏠 Аренда
    if message.text == "🏠 Аренда":

        if not await has_access(user_id):
            await message.answer("🔒 Доступ закрыт.\nНажмите 🎁 Бесплатно 2 часа")
            return

        await message.answer("🔎 Ищу объявления...")
        await send_results(user_id, "https://krisha.kz/arenda/")
        return

    # 🏡 Продажа
    if message.text == "🏡 Продажа":

        if not await has_access(user_id):
            await message.answer("🔒 Доступ закрыт.\nНажмите 🎁 Бесплатно 2 часа")
            return

        await message.answer("🔎 Ищу объявления...")
        await send_results(user_id, "https://krisha.kz/prodazha/")
        return

# ================= ПОДТВЕРЖДЕНИЕ ОПЛАТЫ =================

@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve(callback: types.CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])
    expire = datetime.now() + timedelta(days=30)

    cursor.execute(
        "UPDATE users SET pro_until=? WHERE user_id=?",
        (expire.isoformat(), user_id)
    )
    db.commit()

    await bot.send_message(
        user_id,
        f"✅ Подписка до {expire.strftime('%d.%m.%Y')}"
    )

    await callback.message.edit_text("✅ Подписка выдана")

# ================= ЗАПУСК =================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

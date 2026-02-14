import os
import asyncpg

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None


@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🏡 Продажа")],
            [types.KeyboardButton(text="🛒 Товары")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "🚀 Бот запущен!\nВыберите категорию:",
        reply_markup=keyboard
    )


@dp.message()
async def handler(message: types.Message):
    await message.answer(f"Вы выбрали: {message.text}")

    await db.execute(
        """
        INSERT INTO users(user_id, username)
        VALUES($1, $2)
        ON CONFLICT (user_id) DO NOTHING
        """,
        message.from_user.id,
        message.from_user.username
    )

async def main():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT
        )
    """)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

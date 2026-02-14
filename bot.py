import asyncio
import os
import asyncpg

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db = None


# ======================
# FSM СОСТОЯНИЯ
# ======================

class AdForm(StatesGroup):
    waiting_for_description = State()


# ======================
# /start
# ======================

@dp.message(Command("start"))
async def start(message: types.Message):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="💰 Продажа")],
            [types.KeyboardButton(text="🛒 Товары")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "🚀 Бот запущен!\nВыберите категорию:",
        reply_markup=keyboard
    )


# ======================
# ВЫБОР КАТЕГОРИИ
# ======================

@dp.message(F.text.in_(["🏠 Аренда", "💰 Продажа", "🛒 Товары"]))
async def choose_category(message: types.Message, state: FSMContext):

    await state.update_data(category=message.text)

    await message.answer("✍️ Напишите описание объявления:")
    await state.set_state(AdForm.waiting_for_description)


# ======================
# ПОЛУЧЕНИЕ ОПИСАНИЯ
# ======================

@dp.message(AdForm.waiting_for_description)
async def save_ad(message: types.Message, state: FSMContext):

    data = await state.get_data()
    category = data.get("category")
    description = message.text

    # Сохраняем пользователя
    await db.execute(
        """
        INSERT INTO users(user_id, username)
        VALUES($1, $2)
        ON CONFLICT (user_id) DO NOTHING
        """,
        message.from_user.id,
        message.from_user.username
    )

    # Сохраняем объявление
    await db.execute(
        """
        INSERT INTO ads(user_id, category, description)
        VALUES($1, $2, $3)
        """,
        message.from_user.id,
        category,
        description
    )

    await message.answer("✅ Объявление сохранено!")

    await state.clear()


# ======================
# MAIN
# ======================

async def main():
    global db

    db = await asyncpg.connect(DATABASE_URL)

    # Таблица пользователей
    await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT
    )
    """)

    # Таблица объявлений
    await db.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        category TEXT,
        description TEXT
    )
    """)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

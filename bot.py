import os
import asyncio
from datetime import datetime, timedelta

import asyncpg
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, Request
import uvicorn

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# ---------------- DATABASE ----------------

class DB:
    pool = None

    @classmethod
    async def connect(cls):
        cls.pool = await asyncpg.create_pool(DATABASE_URL)

    @classmethod
    async def create_tables(cls):
        async with cls.pool.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE,
                username TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                subscription_until TIMESTAMP,
                tariff TEXT DEFAULT 'free',
                trial_used BOOLEAN DEFAULT FALSE,
                region TEXT,
                price_from INTEGER,
                price_to INTEGER
            );
            """)

# ---------------- KEYBOARD ----------------

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Поиск квартир Алматы", callback_data="search")],
        [InlineKeyboardButton(text="⭐ Купить Standard (4990₸)", callback_data="buy_standard")],
        [InlineKeyboardButton(text="🔥 Купить Pro (9990₸)", callback_data="buy_pro")],
        [InlineKeyboardButton(text="🎁 Бесплатно 2 часа", callback_data="trial")]
    ])

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(message: types.Message):
    async with DB.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1,$2)
            ON CONFLICT (user_id) DO NOTHING
        """, message.from_user.id, message.from_user.username)

    await message.answer(
        "Бот недвижимости по Алматы.\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

# ---------------- TRIAL ----------------

@dp.callback_query(lambda c: c.data == "trial")
async def trial(callback: types.CallbackQuery):
    async with DB.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT trial_used FROM users WHERE user_id=$1",
            callback.from_user.id
        )

        if user["trial_used"]:
            await callback.message.answer("Вы уже использовали пробный доступ.")
            return

        expire = datetime.utcnow() + timedelta(hours=2)

        await conn.execute("""
            UPDATE users
            SET subscription_until=$1,
                trial_used=TRUE,
                tariff='standard'
            WHERE user_id=$2
        """, expire, callback.from_user.id)

    await callback.message.answer("Пробный доступ активирован на 2 часа.")

# ---------------- SEARCH ----------------

@dp.callback_query(lambda c: c.data == "search")
async def search(callback: types.CallbackQuery):
    async with DB.pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT subscription_until FROM users WHERE user_id=$1",
            callback.from_user.id
        )

        if not user["subscription_until"] or user["subscription_until"] < datetime.utcnow():
            await callback.message.answer("Подписка не активна.")
            return

    await callback.message.answer("Поиск объявлений по Алматы...")

# ---------------- PARSER WORKER ----------------

async def parser_worker():
    while True:
        async with DB.pool.acquire() as conn:
            users = await conn.fetch(
                "SELECT user_id FROM users WHERE subscription_until > NOW()"
            )

        for user in users:
            await bot.send_message(
                user["user_id"],
                "🏠 Новое объявление в Алматы\nЦена: 300 000₸"
            )

        await asyncio.sleep(30)

# ---------------- STARTUP ----------------

@app.on_event("startup")
async def startup():
    await DB.connect()
    await DB.create_tables()
    asyncio.create_task(parser_worker())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

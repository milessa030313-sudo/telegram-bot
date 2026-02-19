import asyncio
import os
import json
from datetime import datetime, timedelta, timezone

import aiohttp
import asyncpg
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# ================= CONFIG =================

load_dotenv()

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN or not DATABASE_URL:
    raise ValueError("Не заполнены переменные окружения")

bot = Bot(TOKEN)
dp = Dispatcher()

BASE_URL = "https://krisha.kz"
PARSER_INTERVAL = 60

DISTRICTS = {
    "Алмалинский": "almalinskij",
    "Бостандыкский": "bostandykskij",
    "Ауэзовский": "aujezovskij",
    "Медеуский": "medeuskij",
    "Турксибский": "turksibskij",
    "Жетысуский": "zhetysuskiy",
    "Алатауский": "alatauskij",
    "Наурызбайский": "nauryzbajskij",
}

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ================= DATABASE =================

async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            mode TEXT,
            district TEXT,
            subscription_until TIMESTAMP
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS sent_ads(
            user_id BIGINT,
            ad_id TEXT,
            PRIMARY KEY(user_id, ad_id)
        );
        """)

# ================= PARSER =================

async def parse(mode="rent", district=None):
    base_path = "arenda/kvartiry/almaty/" if mode == "rent" else "prodazha/kvartiry/almaty/"

    if district:
        url = f"{BASE_URL}/{base_path}{district}/"
    else:
        url = f"{BASE_URL}/{base_path}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
            html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".a-card")

    ads = []
    for card in cards[:15]:
        try:
            link = card.select_one("a").get("href")
            if not link.startswith("http"):
                link = BASE_URL + link

            ad_id = link.split("/")[-1]
            title = card.select_one(".a-card__title").text.strip()

            ads.append({
                "id": ad_id,
                "text": f"🏠 {title}\n{link}"
            })
        except:
            continue

    return ads

# ================= SENDER =================

async def sender_job():
    async with pool.acquire() as conn:
        users = await conn.fetch("""
        SELECT * FROM users
        WHERE subscription_until > $1
        """, utcnow())

    for user in users:

        ads = await parse(user["mode"], user["district"])

        async with pool.acquire() as conn:
            for ad in ads:
                exists = await conn.fetchval("""
                SELECT 1 FROM sent_ads
                WHERE user_id=$1 AND ad_id=$2
                """, user["user_id"], ad["id"])

                if exists:
                    continue

                try:
                    await bot.send_message(user["user_id"], ad["text"])

                    await conn.execute("""
                    INSERT INTO sent_ads(user_id, ad_id)
                    VALUES($1,$2)
                    """, user["user_id"], ad["id"])

                    await asyncio.sleep(0.3)

                except:
                    continue

# ================= USER FLOW =================

@dp.message(Command("start"))
async def start(message: Message):
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users(user_id)
        VALUES($1)
        ON CONFLICT DO NOTHING
        """, message.from_user.id)

    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(text="🏠 Аренда", callback_data="rent"),
        InlineKeyboardButton(text="🏡 Продажа", callback_data="sale")
    )
    kb.adjust(2)

    await message.answer("Выберите режим:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.in_(["rent", "sale"]))
async def set_mode(callback: CallbackQuery):
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET mode=$1 WHERE user_id=$2
        """, callback.data, callback.from_user.id)

    kb = InlineKeyboardBuilder()
    for name, code in DISTRICTS.items():
        kb.add(InlineKeyboardButton(text=name, callback_data=f"district_{code}"))
    kb.adjust(2)

    await callback.message.edit_text("Выберите район:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("district_"))
async def set_district(callback: CallbackQuery):
    district_code = callback.data.replace("district_", "")

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET district=$1 WHERE user_id=$2
        """, district_code, callback.from_user.id)

    await callback.message.edit_text(
        "✅ Район сохранён.\n\nДля активации подписки отправьте /buy"
    )

@dp.message(Command("buy"))
async def buy(message: Message):
    until = utcnow() + timedelta(days=30)

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET subscription_until=$1
        WHERE user_id=$2
        """, until, message.from_user.id)

    await message.answer("💎 Подписка активирована на 30 дней!")

# ================= MAIN =================

async def main():
    global pool

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=3, max_size=10)
    await init_db(pool)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(sender_job, "interval", seconds=PARSER_INTERVAL)
    scheduler.start()

    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

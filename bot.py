import asyncio
import os
import json
from datetime import datetime, timedelta, timezone

import aiohttp
import asyncpg
import redis.asyncio as redis
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

if not TOKEN or not ADMIN_ID or not DATABASE_URL or not REDIS_URL:
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
}

ROOMS = ["1", "2", "3", "4"]


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ================= DATABASE =================

async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            mode TEXT DEFAULT 'rent',
            district TEXT,
            rooms TEXT,
            tariff TEXT DEFAULT 'free',
            subscription_until TIMESTAMP
        );
        """)


# ================= PARSER =================

async def parse(mode="rent"):
    path = "arenda/kvartiry/almaty/" if mode == "rent" else "prodazha/kvartiry/almaty/"
    url = f"{BASE_URL}/{path}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
            html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".a-card")

    ads = []
    for card in cards[:20]:
        try:
            link = card.select_one("a").get("href")
            if not link.startswith("http"):
                link = BASE_URL + link
            ad_id = link.split("/")[-1]
            title = card.select_one(".a-card__title").text.strip()

            ads.append({
                "id": ad_id,
                "text": f"{title}\n{link}"
            })
        except:
            continue

    return ads


# ================= AUTO PARSER =================

async def parser_job():
    rent_ads = await parse("rent")
    sale_ads = await parse("sale")

    await redis_client.set("rent_ads", json.dumps(rent_ads))
    await redis_client.set("sale_ads", json.dumps(sale_ads))


# ================= AUTO SEND =================

async def sender_job():
    async with pool.acquire() as conn:
        users = await conn.fetch("""
        SELECT * FROM users
        WHERE subscription_until > $1
        """, utcnow())

    for user in users:
        ads_json = await redis_client.get(f"{user['mode']}_ads")
        if not ads_json:
            continue

        ads = json.loads(ads_json)

        for ad in ads[:3]:
            await bot.send_message(user["user_id"], ad["text"])
            await asyncio.sleep(0.3)


# ================= ADMIN PANEL =================

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    kb.add(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    kb.adjust(1)

    await message.answer("Админ панель:", reply_markup=kb.as_markup())


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        paid = await conn.fetchval("""
            SELECT COUNT(*) FROM users
            WHERE subscription_until > $1
        """, utcnow())

    await callback.message.edit_text(
        f"👥 Всего пользователей: {total}\n💎 Активных подписок: {paid}"
    )


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.answer("Отправьте текст для рассылки:")
    dp["broadcast"] = True


@dp.message()
async def handle_messages(message: Message):
    if dp.get("broadcast") and message.from_user.id == ADMIN_ID:
        dp["broadcast"] = False

        async with pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id FROM users")

        for user in users:
            try:
                await bot.send_message(user["user_id"], message.text)
                await asyncio.sleep(0.1)
            except:
                continue

        await message.answer("Рассылка завершена")


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
    kb.add(InlineKeyboardButton(text="🏠 Аренда", callback_data="rent"))
    kb.add(InlineKeyboardButton(text="🏡 Продажа", callback_data="sale"))
    kb.adjust(2)

    await message.answer("Выберите режим:", reply_markup=kb.as_markup())


@dp.callback_query(F.data.in_(["rent", "sale"]))
async def set_mode(callback: CallbackQuery):
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET mode=$1 WHERE user_id=$2
        """, callback.data, callback.from_user.id)

    await callback.message.edit_text("Режим сохранён")


@dp.message(Command("buy"))
async def buy(message: Message):
    until = utcnow() + timedelta(days=30)

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET tariff='standard', subscription_until=$1
        WHERE user_id=$2
        """, until, message.from_user.id)

    await message.answer("💎 Подписка активирована на 30 дней!")


# ================= MAIN =================

async def main():
    global pool, redis_client

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    redis_client = redis.from_url(REDIS_URL)

    await init_db(pool)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(parser_job, "interval", seconds=PARSER_INTERVAL)
    scheduler.add_job(sender_job, "interval", seconds=65)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

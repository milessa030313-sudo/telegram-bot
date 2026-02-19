import asyncio
import os
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

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

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
            subscription_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

# ================= PARSER =================

async def parse(mode="rent"):
    path = "arenda/kvartiry/almaty/" if mode=="rent" else "prodazha/kvartiry/almaty/"
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

# ================= AUTO SEND =================

async def sender_job():
    async with pool.acquire() as conn:
        users = await conn.fetch("""
        SELECT * FROM users
        WHERE subscription_until > $1
        """, utcnow())

    for user in users:
        ads = await parse(user["mode"])

        for ad in ads[:3]:
            try:
                await bot.send_message(user["user_id"], ad["text"])
                await asyncio.sleep(0.3)
            except:
                continue

# ================= USER HANDLERS =================

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

@dp.callback_query(F.data.in_(["rent","sale"]))
async def set_mode(callback: CallbackQuery):
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET mode=$1 WHERE user_id=$2
        """, callback.data, callback.from_user.id)

    kb = InlineKeyboardBuilder()
    for d in DISTRICTS:
        kb.add(InlineKeyboardButton(text=d, callback_data=f"district_{DISTRICTS[d]}"))
    kb.adjust(2)

    await callback.message.edit_text("Выберите район:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("district_"))
async def set_district(callback: CallbackQuery):
    district = callback.data.split("_")[1]

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET district=$1 WHERE user_id=$2
        """, district, callback.from_user.id)

    kb = InlineKeyboardBuilder()
    for r_ in ROOMS:
        kb.add(InlineKeyboardButton(text=f"{r_} комн", callback_data=f"rooms_{r_}"))
    kb.adjust(2)

    await callback.message.edit_text("Выберите комнаты:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("rooms_"))
async def set_rooms(callback: CallbackQuery):
    rooms = callback.data.split("_")[1]

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET rooms=$1 WHERE user_id=$2
        """, rooms, callback.from_user.id)

    await callback.message.edit_text("✅ Фильтр сохранен.\n\nИспользуйте /buy для подписки.")

# ================= BUY =================

@dp.message(Command("buy"))
async def buy(message: Message):
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="💎 Standard 4900₸", callback_data="buy_standard"))
    kb.adjust(1)

    await message.answer("Оплата Kaspi: XXXX XXXX XXXX\nПосле оплаты напишите админу.",
                         reply_markup=kb.as_markup())

@dp.callback_query(F.data=="buy_standard")
async def activate(callback: CallbackQuery):
    until = utcnow() + timedelta(days=30)

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users SET tariff='standard', subscription_until=$1
        WHERE user_id=$2
        """, until, callback.from_user.id)

    await callback.message.edit_text("🎉 Подписка активирована на 30 дней!")

# ================= ADMIN PANEL =================

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Активные", callback_data="admin_active")
    )
    kb.adjust(1)
    return kb.as_markup()

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("⚙️ Админ панель", reply_markup=admin_kb())

@dp.callback_query(F.data=="admin_stats")
async def stats(callback: CallbackQuery):
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        active = await conn.fetchval("""
        SELECT COUNT(*) FROM users
        WHERE subscription_until > $1
        """, utcnow())

    await callback.message.edit_text(
        f"Всего пользователей: {total}\nАктивных подписок: {active}",
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data=="admin_active")
async def active(callback: CallbackQuery):
    async with pool.acquire() as conn:
        users = await conn.fetch("""
        SELECT user_id FROM users
        WHERE subscription_until > $1
        LIMIT 20
        """, utcnow())

    text = "Активные:\n"
    for u in users:
        text += f"{u['user_id']}\n"

    await callback.message.edit_text(text, reply_markup=admin_kb())

# ================= MAIN =================

async def main():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    await init_db(pool)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(sender_job, "interval", seconds=PARSER_INTERVAL)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

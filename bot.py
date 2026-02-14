import asyncio
import os
import aiohttp
import asyncpg
import xml.etree.ElementTree as ET
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None

RENT_RSS = "https://krisha.kz/arenda/kvartiry/almaty/?rss=1"
SALE_RSS = "https://krisha.kz/prodazha/kvartiry/almaty/?rss=1"

# ================= БАЗА =================

async def init_db():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        )
    """)

async def add_user(user_id):
    await db.execute("""
        INSERT INTO users(user_id)
        VALUES($1)
        ON CONFLICT (user_id) DO NOTHING
    """, user_id)

async def get_users():
    rows = await db.fetch("SELECT user_id FROM users")
    return [r["user_id"] for r in rows]

# ================= RSS ПАРСЕР =================

async def parse_rss(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            text = await response.text()

    root = ET.fromstring(text)

    items = []
    for item in root.findall(".//item")[:10]:
        title = item.find("title").text
        link = item.find("link").text
        ad_id = link.split("/")[-1]

        items.append({
            "id": ad_id,
            "title": title,
            "link": link
        })

    return items

# ================= КНОПКИ =================

@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🏡 Продажа")]
        ],
        resize_keyboard=True
    )

    await add_user(message.from_user.id)

    await message.answer(
        "🚀 Бот запущен\nВыберите категорию:",
        reply_markup=keyboard
    )

# ================= ОБРАБОТКА =================

@dp.message()
async def handler(message: types.Message):

    if message.text == "🏠 Аренда":
        await message.answer("🔎 Ищу аренду...")
        ads = await parse_rss(RENT_RSS)

    elif message.text == "🏡 Продажа":
        await message.answer("🔎 Ищу продажу...")
        ads = await parse_rss(SALE_RSS)

    else:
        return

    if not ads:
        await message.answer("❌ Объявления не найдены.")
        return

    for ad in ads:
        text = f"🏠 {ad['title']}\n\n🔗 {ad['link']}"
        await message.answer(text)

# ================= АВТО УВЕДОМЛЕНИЯ =================

last_rent_ids = set()
last_sale_ids = set()

async def auto_parser():
    global last_rent_ids, last_sale_ids

    while True:
        try:
            users = await get_users()

            rent_ads = await parse_rss(RENT_RSS)
            sale_ads = await parse_rss(SALE_RSS)

            for ad in rent_ads:
                if ad["id"] not in last_rent_ids:
                    last_rent_ids.add(ad["id"])
                    for user in users:
                        await bot.send_message(
                            user,
                            f"🔥 Новая аренда!\n\n{ad['title']}\n\n{ad['link']}"
                        )

            for ad in sale_ads:
                if ad["id"] not in last_sale_ids:
                    last_sale_ids.add(ad["id"])
                    for user in users:
                        await bot.send_message(
                            user,
                            f"🔥 Новая продажа!\n\n{ad['title']}\n\n{ad['link']}"
                        )

        except Exception as e:
            print("Ошибка авто-парсера:", e)

        await asyncio.sleep(60)

# ================= MAIN =================

async def main():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await init_db()

    asyncio.create_task(auto_parser())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

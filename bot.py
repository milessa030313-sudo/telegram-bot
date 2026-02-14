import asyncio
import os
import aiohttp
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from bs4 import BeautifulSoup

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None

RENT_URL = "https://krisha.kz/arenda/kvartiry/almaty/"
SALE_URL = "https://krisha.kz/prodazha/kvartiry/almaty/"

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

# ================= ПАРСЕР =================

async def parse_krisha(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
        "Accept-Language": "ru-RU,ru;q=0.9"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="a-card__inc")

    results = []

    for card in cards:
        link_tag = card.find("a", class_="a-card__title")
        if not link_tag:
            continue

        title = link_tag.text.strip()
        href = link_tag.get("href")

        if not href:
            continue

        full_link = "https://krisha.kz" + href
        ad_id = href.split("/")[-1]

        results.append({
            "id": ad_id,
            "title": title,
            "link": full_link
        })

    return results[:10]

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
        ads = await parse_krisha(RENT_URL)

    elif message.text == "🏡 Продажа":
        await message.answer("🔎 Ищу продажу...")
        ads = await parse_krisha(SALE_URL)

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

            rent_ads = await parse_krisha(RENT_URL)
            sale_ads = await parse_krisha(SALE_URL)

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

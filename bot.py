import asyncio
import os
import asyncpg
import aiohttp
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None


# =========================
# СТАРТ
# =========================

@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🏢 Продажа")]
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите категорию:", reply_markup=keyboard)


# =========================
# СОХРАНЕНИЕ ВЫБОРА
# =========================

@dp.message()
async def choose_category(message: types.Message):
    if message.text not in ["🏠 Аренда", "🏢 Продажа"]:
        return

    await db.execute("""
        INSERT INTO users(user_id, username, category)
        VALUES($1, $2, $3)
        ON CONFLICT (user_id)
        DO UPDATE SET category=$3
    """,
        message.from_user.id,
        message.from_user.username,
        message.text
    )

    await message.answer("Категория сохранена ✅")


# =========================
# ПАРСЕР
# =========================

async def parse(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    ads = []
    cards = soup.find_all("a", class_="a-card__title")[:5]

    for card in cards:
        title = card.text.strip()
        link = "https://krisha.kz" + card["href"]

        ads.append(f"🏠 Новое объявление:\n{title}\n{link}")

    return ads


async def parse_arenda():
    return await parse("https://krisha.kz/arenda/kvartiry/almaty/")


async def parse_prodazha():
    return await parse("https://krisha.kz/prodazha/kvartiry/almaty/")


# =========================
# УВЕДОМЛЕНИЯ
# =========================

async def notify_users():
    while True:
        users = await db.fetch("SELECT user_id, category FROM users")

        for user in users:
            if user["category"] == "🏠 Аренда":
                ads = await parse_arenda()
            else:
                ads = await parse_prodazha()

            for ad in ads:
                try:
                    await bot.send_message(user["user_id"], ad)
                except:
                    pass

        await asyncio.sleep(300)  # каждые 5 минут


# =========================
# MAIN
# =========================

async def main():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            category TEXT
        )
    """)

    asyncio.create_task(notify_users())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

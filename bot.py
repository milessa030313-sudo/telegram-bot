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


# -------- ПАРСЕР KRISHA --------

async def parse_krisha():
    url = "https://krisha.kz/arenda/kvartiry/almaty/"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    ads = soup.find_all("a", class_="a-card__title")

    results = []

    for ad in ads[:5]:
        link = "https://krisha.kz" + ad.get("href")
        title = ad.text.strip()
        results.append(f"{title}\n{link}")

    return results


# -------- ФОНОВАЯ ПРОВЕРКА --------

async def notify_users():
    while True:
        ads = await parse_krisha()

        users = await db.fetch("SELECT user_id FROM users")

        for user in users:
            for ad in ads:
                await bot.send_message(user["user_id"], f"🏠 Новое объявление:\n\n{ad}")

        await asyncio.sleep(300)  # каждые 5 минут


# -------- БОТ --------

@dp.message(Command("start"))
async def start(message: types.Message):
    await db.execute("""
        INSERT INTO users(user_id, username)
        VALUES($1, $2)
        ON CONFLICT (user_id) DO NOTHING
    """, message.from_user.id, message.from_user.username)

    await message.answer("Бот запущен ✅\nСкоро будут объявления...")


async def main():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT
        )
    """)

    asyncio.create_task(notify_users())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

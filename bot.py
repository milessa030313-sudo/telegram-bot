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

# ==========================
# URLЫ ДЛЯ ПАРСИНГА
# ==========================

RENT_URL = "https://krisha.kz/arenda/kvartiry/almaty/"
SALE_URL = "https://krisha.kz/prodazha/kvartiry/almaty/"

# ==========================
# ПАРСЕР
# ==========================

async def parse_krisha(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("a", class_="a-card__title")

    results = []

    for card in cards[:10]:
        link = "https://krisha.kz" + card.get("href")
        title = card.text.strip()

        ad_id = link.split("/")[-1]

        results.append({
            "id": ad_id,
            "title": title,
            "link": link
        })

    return results


# ==========================
# СОХРАНЕНИЕ ПОЛЬЗОВАТЕЛЯ
# ==========================

@dp.message(Command("start"))
async def start(message: types.Message):
    await db.execute("""
        INSERT INTO users(user_id)
        VALUES($1)
        ON CONFLICT (user_id) DO NOTHING
    """, message.from_user.id)

    await message.answer("🚀 Авто-уведомления запущены!\nТеперь новые объявления будут приходить автоматически.")


# ==========================
# ФОНОВЫЙ АВТО-ПАРСЕР
# ==========================

async def auto_parser():
    while True:
        print("Проверка новых объявлений...")

        rent_ads = await parse_krisha(RENT_URL)
        sale_ads = await parse_krisha(SALE_URL)

        users = await db.fetch("SELECT user_id FROM users")

        # Проверяем аренду
        for ad in rent_ads:
            exists = await db.fetchrow("SELECT 1 FROM ads WHERE ad_id=$1", ad["id"])

            if not exists:
                await db.execute("INSERT INTO ads(ad_id) VALUES($1)", ad["id"])

                for user in users:
                    try:
                        await bot.send_message(
                            user["user_id"],
                            f"🏠 Новая аренда:\n{ad['title']}\n{ad['link']}"
                        )
                    except:
                        pass

        # Проверяем продажу
        for ad in sale_ads:
            exists = await db.fetchrow("SELECT 1 FROM ads WHERE ad_id=$1", ad["id"])

            if not exists:
                await db.execute("INSERT INTO ads(ad_id) VALUES($1)", ad["id"])

                for user in users:
                    try:
                        await bot.send_message(
                            user["user_id"],
                            f"🏡 Новая продажа:\n{ad['title']}\n{ad['link']}"
                        )
                    except:
                        pass

        await asyncio.sleep(30)  # Проверка каждые 30 секунд


# ==========================
# MAIN
# ==========================

async def main():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            ad_id TEXT PRIMARY KEY
        )
    """)

    asyncio.create_task(auto_parser())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

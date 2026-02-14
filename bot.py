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

RENT_URL = "https://krisha.kz/arenda/kvartiry/almaty/"
SALE_URL = "https://krisha.kz/prodazha/kvartiry/almaty/"

async def parse_krisha(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    results = []

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if "/show/" in href:
            full_link = "https://krisha.kz" + href
            ad_id = href.split("/")[-1]

            title = link.text.strip()
            if not title:
                continue

            results.append({
                "id": ad_id,
                "title": title,
                "link": full_link
            })

    return results[:10]


@dp.message(Command("start"))
async def start(message: types.Message):
    await db.execute("""
        INSERT INTO users(user_id)
        VALUES($1)
        ON CONFLICT (user_id) DO NOTHING
    """, message.from_user.id)

    await message.answer("🚀 Авто-уведомления активированы!")


async def auto_parser():
    while True:
        print("Проверка новых объявлений...")

        rent_ads = await parse_krisha(RENT_URL)
        sale_ads = await parse_krisha(SALE_URL)

        users = await db.fetch("SELECT user_id FROM users")

        for ad in rent_ads:
            exists = await db.fetchrow(
                "SELECT 1 FROM ads WHERE ad_id=$1", ad["id"]
            )

            if not exists:
                await db.execute(
                    "INSERT INTO ads(ad_id) VALUES($1)",
                    ad["id"]
                )

                for user in users:
                    try:
                        await bot.send_message(
                            user["user_id"],
                            f"🏠 Аренда:\n{ad['title']}\n{ad['link']}"
                        )
                    except:
                        pass

        for ad in sale_ads:
            exists = await db.fetchrow(
                "SELECT 1 FROM ads WHERE ad_id=$1", ad["id"]
            )

            if not exists:
                await db.execute(
                    "INSERT INTO ads(ad_id) VALUES($1)",
                    ad["id"]
                )

                for user in users:
                    try:
                        await bot.send_message(
                            user["user_id"],
                            f"🏡 Продажа:\n{ad['title']}\n{ad['link']}"
                        )
                    except:
                        pass

        await asyncio.sleep(30)


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

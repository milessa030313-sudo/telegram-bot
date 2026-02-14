import asyncio
import os
import aiohttp
import asyncpg
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None


# =======================
# ПАРСЕР KRISHA
# =======================

async def parse_krisha(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    cards = soup.find_all("a", class_="a-card__link")[:5]

    results = []

    for card in cards:
        link = "https://krisha.kz" + card.get("href")

        title_block = card.find_parent("div", class_="a-card__descr")

        if title_block:
            title = title_block.find("a").text.strip()
            price = title_block.find("div", class_="a-card__price").text.strip()

            text = f"""
🏠 Новое объявление:

{title}
💰 {price}

🔗 {link}
"""
            results.append(text)

    return results


# =======================
# /start
# =======================

@dp.message(Command("start"))
async def start(message: types.Message):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🌳 Продажа")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Выберите категорию:",
        reply_markup=keyboard
    )


# =======================
# ОБРАБОТЧИК
# =======================

@dp.message()
async def handler(message: types.Message):

    text = message.text.lower()

    if "аренда" in text:
        await message.answer("🔎 Ищу аренду...")

        url = "https://krisha.kz/arenda/kvartiry/almaty/"
        data = await parse_krisha(url)

        if not data:
            await message.answer("Объявления не найдены.")
            return

        for item in data:
            await message.answer(item)

    elif "продажа" in text:
        await message.answer("🔎 Ищу продажу...")

        url = "https://krisha.kz/prodazha/kvartiry/almaty/"
        data = await parse_krisha(url)

        if not data:
            await message.answer("Объявления не найдены.")
            return

        for item in data:
            await message.answer(item)


# =======================
# MAIN
# =======================

async def main():
    global db

    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT
        )
    """)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

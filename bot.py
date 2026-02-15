import asyncio
import os
import aiohttp
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# =================== ПАРСЕР ===================

async def parse_krisha(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    cards = soup.find_all("div", class_="a-card__inc")

    results = []

    for card in cards[:5]:
        title_tag = card.find("a", class_="a-card__title")
        price_tag = card.find("div", class_="a-card__price")

        if not title_tag or not price_tag:
            continue

        title = title_tag.text.strip()
        price = price_tag.text.strip()
        link = "https://krisha.kz" + title_tag.get("href")

        text = f"""
🏠 Новое объявление:

{title}
💰 {price}

🔗 {link}
"""
        results.append(text)

    return results


# =================== START ===================

@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🏡 Продажа")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "🚀 Бот недвижимости\nВыберите категорию:",
        reply_markup=keyboard
    )


# =================== ОБРАБОТКА ===================

@dp.message()
async def handler(message: types.Message):

    if message.text == "🏠 Аренда":

        await message.answer("🔎 Ищу аренду...")

        url = "https://krisha.kz/arenda/kvartiry/almaty/"
        results = await parse_krisha(url)

        if not results:
            await message.answer("❌ Объявления не найдены.")
            return

        for item in results:
            await message.answer(item)


    elif message.text == "🏡 Продажа":

        await message.answer("🔎 Ищу продажу...")

        url = "https://krisha.kz/prodazha/kvartiry/almaty/"
        results = await parse_krisha(url)

        if not results:
            await message.answer("❌ Объявления не найдены.")
            return

        for item in results:
            await message.answer(item)


# =================== ЗАПУСК ===================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

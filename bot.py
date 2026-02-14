import asyncio
import os
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ====== ПАРСЕР ======
async def parse_krisha(url):
    results = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    cards = soup.find_all("a", class_="a-card__title")

    for card in cards[:5]:
        title = card.text.strip()
        link = "https://krisha.kz" + card.get("href")

        results.append(f"{title}\n{link}")

    return results


# ====== КНОПКИ ======
@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🏢 Продажа")],
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите категорию:", reply_markup=keyboard)


# ====== ОБРАБОТКА ======
@dp.message()
async def handler(message: types.Message):

    if message.text == "🏠 Аренда":
        await message.answer("Ищу аренду...")
        url = "https://krisha.kz/arenda/kvartiry/almaty/"
        data = await parse_krisha(url)

        for item in data:
            await message.answer(item)

    elif message.text == "🏢 Продажа":
        await message.answer("Ищу продажу...")
        url = "https://krisha.kz/prodazha/kvartiry/almaty/"
        data = await parse_krisha(url)

        for item in data:
            await message.answer(item)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

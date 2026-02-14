import asyncio
import os
import json
import re
import aiohttp
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ======== ПАРСЕР KRISHA (ПРОФЕССИОНАЛЬНЫЙ JSON) =========

async def parse_krisha(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script")

    data_script = None

    for script in scripts:
        if script.string and "window.__INITIAL_STATE__" in script.string:
            data_script = script.string
            break

    if not data_script:
        return []

    match = re.search(r"window.__INITIAL_STATE__ = (.*);", data_script)

    if not match:
        return []

    data = json.loads(match.group(1))

    offers = data.get("search", {}).get("offers", [])

    results = []

    for offer in offers[:5]:
        title = offer.get("title", "Без названия")
        price = offer.get("price", "Без цены")
        offer_id = offer.get("id")

        link = f"https://krisha.kz/a/show/{offer_id}"

        text = f"""
🏠 Новое объявление:

{title}
💰 {price} ₸

🔗 {link}
"""
        results.append(text)

    return results


# ========= START =========

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


# ========= ОБРАБОТЧИК =========

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


# ========= ЗАПУСК =========

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

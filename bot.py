import asyncio
import os
import aiohttp
import xml.etree.ElementTree as ET

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# RSS ссылки
RENT_RSS = "https://krisha.kz/arenda/kvartiry/almaty/?rss=1"
SALE_RSS = "https://krisha.kz/prodazha/kvartiry/almaty/?rss=1"


# ---------- Парсер RSS ----------
async def parse_rss(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return []

                text = await response.text()

        root = ET.fromstring(text)

        items = []
        for item in root.findall(".//item")[:10]:
            title = item.find("title")
            link = item.find("link")

            if title is not None and link is not None:
                items.append({
                    "title": title.text,
                    "link": link.text
                })

        return items

    except Exception as e:
        print("RSS ошибка:", e)
        return []


# ---------- Старт ----------
@dp.message(commands=["start"])
async def start(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Аренда")],
            [KeyboardButton(text="🏡 Продажа")]
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите категорию:", reply_markup=keyboard)


# ---------- Обработчик кнопок ----------
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
        await message.answer("❌ Объявления не найдены или сайт временно недоступен.")
        return

    for ad in ads:
        await message.answer(
            f"{ad['title']}\n\n{ad['link']}"
        )


# ---------- Запуск ----------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

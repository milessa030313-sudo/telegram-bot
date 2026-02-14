import asyncio
import os
import aiohttp
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# =======================
# ПАРСЕР АРЕНДА
# =======================
async def parse_arenda():
    url = "https://krisha.kz/arenda/kvartiry/almaty/"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("div", class_="a-card")

    ads = []

    for item in items[:5]:
        title = item.find("a", class_="a-card__title")
        price = item.find("div", class_="a-card__price")

        if title and price:
            ads.append({
                "title": title.text.strip(),
                "price": price.text.strip(),
                "link": "https://krisha.kz" + title.get("href")
            })

    return ads


# =======================
# ПАРСЕР ПРОДАЖА
# =======================
async def parse_prodazha():
    url = "https://krisha.kz/prodazha/kvartiry/almaty/"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("div", class_="a-card")

    ads = []

    for item in items[:5]:
        title = item.find("a", class_="a-card__title")
        price = item.find("div", class_="a-card__price")

        if title and price:
            ads.append({
                "title": title.text.strip(),
                "price": price.text.strip(),
                "link": "https://krisha.kz" + title.get("href")
            })

    return ads


# =======================
# СТАРТ
# =======================
@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🏢 Продажа")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "🚀 Бот запущен!\nВыберите категорию:",
        reply_markup=keyboard
    )


# =======================
# ОБРАБОТКА КНОПОК
# =======================
@dp.message()
async def handler(message: types.Message):

    if message.text == "🏠 Аренда":
        await message.answer("🔎 Ищу объявления по аренде...")

        ads = await parse_arenda()

        if not ads:
            await message.answer("❌ Объявления не найдены")
            return

        for ad in ads:
            text = (
                f"🏠 Новое объявление:\n\n"
                f"{ad['title']}\n"
                f"{ad['price']}\n"
                f"{ad['link']}"
            )
            await message.answer(text)

    elif message.text == "🏢 Продажа":
        await message.answer("🔎 Ищу объявления по продаже...")

        ads = await parse_prodazha()

        if not ads:
            await message.answer("❌ Объявления не найдены")
            return

        for ad in ads:
            text = (
                f"🏢 Новое объявление:\n\n"
                f"{ad['title']}\n"
                f"{ad['price']}\n"
                f"{ad['link']}"
            )
            await message.answer(text)

    else:
        return


# =======================
# ЗАПУСК
# =======================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

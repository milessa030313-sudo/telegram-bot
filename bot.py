import asyncio
import os
import aiohttp
import sqlite3
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== БАЗА ==================

db = sqlite3.connect("database.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 1,
    mode TEXT DEFAULT 'rent'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_links(
    link TEXT PRIMARY KEY
)
""")

db.commit()

# ================== КНОПКИ ==================

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Аренда (от хозяев)")],
        [KeyboardButton(text="🏡 Продажа (от хозяев)")],
        [KeyboardButton(text="⛔ Стоп"), KeyboardButton(text="▶️ Запустить")]
    ],
    resize_keyboard=True
)

# ================== ПАРСЕР ==================

async def parse(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.a-card")

    results = []

    for card in cards[:5]:
        title_tag = card.select_one("a.a-card__title")
        price_tag = card.select_one("div.a-card__price")

        if not title_tag or not price_tag:
            continue

        title = title_tag.text.strip()
        price = price_tag.text.strip()
        link = "https://krisha.kz" + title_tag.get("href")

        results.append((title, price, link))

    return results

# ================== СТАРТ ==================

@dp.message(Command("start"))
async def start(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (message.from_user.id,))
    cursor.execute("UPDATE users SET active=1 WHERE user_id=?", (message.from_user.id,))
    db.commit()

    await message.answer(
        "🚀 Бот недвижимости Алматы\n"
        "Квартиры ТОЛЬКО от хозяев\n"
        "Авто‑проверка каждые 2 минуты",
        reply_markup=keyboard
    )

# ================== ОБРАБОТКА ==================

@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id

    # СТОП
    if message.text == "⛔ Стоп":
        cursor.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("❌ Авто‑поиск остановлен.")
        return

    # ЗАПУСТИТЬ
    if message.text == "▶️ Запустить":
        cursor.execute("UPDATE users SET active=1 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("✅ Авто‑поиск снова активен.")
        return

    # АРЕНДА
    if message.text == "🏠 Аренда (от хозяев)":
        cursor.execute("UPDATE users SET mode='rent' WHERE user_id=?", (user_id,))
        db.commit()

        await send_results(
            user_id,
            "https://krisha.kz/arenda/kvartiry/almaty/?das[who]=1"
        )
        return

    # ПРОДАЖА
    if message.text == "🏡 Продажа (от хозяев)":
        cursor.execute("UPDATE users SET mode='sale' WHERE user_id=?", (user_id,))
        db.commit()

        await send_results(
            user_id,
            "https://krisha.kz/prodazha/kvartiry/almaty/?das[who]=1"
        )
        return

# ================== ОТПРАВКА ==================

async def send_results(user_id, url):
    results = await parse(url)

    if not results:
        await bot.send_message(user_id, "❌ Объявления не найдены.")
        return

    for title, price, link in results:
        cursor.execute("SELECT link FROM sent_links WHERE link=?", (link,))
        if cursor.fetchone():
            continue

        cursor.execute("INSERT INTO sent_links(link) VALUES(?)", (link,))
        db.commit()

        text = f"""
🏠 {title}
💰 {price}
🔗 {link}
"""
        await bot.send_message(user_id, text)

# ================== МОНИТОР ==================

async def monitor():
    await asyncio.sleep(10)

    while True:
        try:
            cursor.execute("SELECT user_id, mode FROM users WHERE active=1")
            users = cursor.fetchall()

            for user_id, mode in users:

                if mode == "rent":
                    url = "https://krisha.kz/arenda/kvartiry/almaty/?das[who]=1"
                else:
                    url = "https://krisha.kz/prodazha/kvartiry/almaty/?das[who]=1"

                await send_results(user_id, url)

            await asyncio.sleep(120)

        except Exception as e:
            print("Ошибка:", e)
            await asyncio.sleep(60)

# ================== ЗАПУСК ==================

async def main():
    asyncio.create_task(monitor())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

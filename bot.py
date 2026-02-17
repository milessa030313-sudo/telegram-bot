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
    mode TEXT DEFAULT 'rent',
    rooms TEXT DEFAULT '1',
    district TEXT DEFAULT '1'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_links(
    link TEXT PRIMARY KEY
)
""")

db.commit()

# ================== КНОПКИ ==================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Аренда"), KeyboardButton(text="🏡 Продажа")],
        [
            KeyboardButton(text="1️⃣ 1"),
            KeyboardButton(text="2️⃣ 2"),
            KeyboardButton(text="3️⃣ 3")
        ],
        [
            KeyboardButton(text="4️⃣ 4"),
            KeyboardButton(text="5️⃣ 5+")
        ],
        [KeyboardButton(text="⛔ Стоп")]
    ],
    resize_keyboard=True
)

district_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Алатауский")],
        [KeyboardButton(text="Алмалинский")],
        [KeyboardButton(text="Ауэзовский")],
        [KeyboardButton(text="Бостандыкский")],
        [KeyboardButton(text="Жетысуский")],
        [KeyboardButton(text="Медеуский")],
        [KeyboardButton(text="Наурызбайский")],
        [KeyboardButton(text="Турксибский")],
        [KeyboardButton(text="⬅ Назад")]
    ],
    resize_keyboard=True
)

# ================== РАЙОНЫ ==================

district_map = {
    "Алмалинский": "1",
    "Ауэзовский": "2",
    "Бостандыкский": "3",
    "Жетысуский": "4",
    "Медеуский": "5",
    "Наурызбайский": "6",
    "Турксибский": "7",
    "Алатауский": "8"
}

# ================== URL ==================

def build_url(mode, rooms, district):

    if mode == "rent":
        base = "https://krisha.kz/arenda/kvartiry/almaty/?das[who]=1"
    else:
        base = "https://krisha.kz/prodazha/kvartiry/almaty/?das[who]=1"

    if rooms == "5":
        return base + f"&das[live.rooms]=5&das[region]={district}"
    else:
        return base + f"&das[live.rooms]={rooms}&das[region]={district}"

# ================== ПАРСЕР ==================

async def parse(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.a-card")

    results = []

    for card in cards:
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
        "🏠 Бот недвижимости Алматы\n"
        "Только от хозяев\n"
        "После выбора фильтра приходит вся первая страница\n"
        "Далее проверка каждые 2 минуты",
        reply_markup=main_keyboard
    )

# ================== ОБРАБОТКА ==================

@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id

    # СТОП
    if message.text == "⛔ Стоп":
        cursor.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("❌ Авто-поиск остановлен.")
        return

    # НАЗАД
    if message.text == "⬅ Назад":
        await message.answer("Выберите количество комнат:", reply_markup=main_keyboard)
        return

    # РЕЖИМ
    if message.text == "🏠 Аренда":
        cursor.execute("UPDATE users SET mode='rent', active=1 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("Выберите количество комнат:")
        return

    if message.text == "🏡 Продажа":
        cursor.execute("UPDATE users SET mode='sale', active=1 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("Выберите количество комнат:")
        return

    # КОМНАТЫ
    room_value = None

    if message.text == "1️⃣ 1":
        room_value = "1"
    elif message.text == "2️⃣ 2":
        room_value = "2"
    elif message.text == "3️⃣ 3":
        room_value = "3"
    elif message.text == "4️⃣ 4":
        room_value = "4"
    elif message.text == "5️⃣ 5+":
        room_value = "5"

    if room_value:
        cursor.execute("UPDATE users SET rooms=? WHERE user_id=?", (room_value, user_id))
        db.commit()

        await message.answer("Выберите район:", reply_markup=district_keyboard)
        return

    # РАЙОН
    if message.text in district_map:

        district_value = district_map[message.text]

        cursor.execute("DELETE FROM sent_links")
        db.commit()

        cursor.execute(
            "UPDATE users SET district=?, active=1 WHERE user_id=?",
            (district_value, user_id)
        )
        db.commit()

        cursor.execute("SELECT mode, rooms FROM users WHERE user_id=?", (user_id,))
        mode, rooms = cursor.fetchone()

        url = build_url(mode, rooms, district_value)

        await message.answer("🔎 Ищем объявления...\n")

        await send_results(user_id, url)
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
            cursor.execute("SELECT user_id, mode, rooms, district FROM users WHERE active=1")
            users = cursor.fetchall()

            for user_id, mode, rooms, district in users:
                url = build_url(mode, rooms, district)
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

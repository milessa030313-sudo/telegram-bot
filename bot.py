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
    district TEXT DEFAULT 'bostandykskij'
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
        [KeyboardButton(text="Алатауский"), KeyboardButton(text="Алмалинский")],
        [KeyboardButton(text="Ауэзовский"), KeyboardButton(text="Бостандыкский")],
        [KeyboardButton(text="Жетысуский"), KeyboardButton(text="Медеуский")],
        [KeyboardButton(text="Наурызбайский"), KeyboardButton(text="Турксибский")],
        [KeyboardButton(text="⬅ Назад")]
    ],
    resize_keyboard=True
)

# ================== SLUG РАЙОНОВ ==================

district_map = {
    "Алмалинский": "almaly",
    "Ауэзовский": "auezovskij",
    "Бостандыкский": "bostandykskij",
    "Жетысуский": "zhetysusky",
    "Медеуский": "medeuskij",
    "Наурызбайский": "nauryzbajskij",
    "Турксибский": "turksibskij",
    "Алатауский": "alatauskij"
}

# ================== URL ==================

def build_url(mode, rooms, district_slug):

    if mode == "rent":
        base = f"https://krisha.kz/arenda/kvartiry/almaty-{district_slug}/"
    else:
        base = f"https://krisha.kz/prodazha/kvartiry/almaty-{district_slug}/"

    return f"{base}?das[live.rooms]={rooms}&das[who]=1"

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
        "🏠 Недвижимость Алматы\n"
        "Аренда / Продажа → Комнаты → Район\n"
        "Мониторинг каждые 2 минуты",
        reply_markup=main_keyboard
    )

# ================== ОБРАБОТКА ==================

@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id

    if message.text == "⛔ Стоп":
        cursor.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("❌ Авто-поиск остановлен.")
        return

    if message.text == "⬅ Назад":
        await message.answer("Выберите количество комнат:", reply_markup=main_keyboard)
        return

    if message.text == "🏠 Аренда":
        cursor.execute("UPDATE users SET mode='rent' WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("Выберите количество комнат:")
        return

    if message.text == "🏡 Продажа":
        cursor.execute("UPDATE users SET mode='sale' WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("Выберите количество комнат:")
        return

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

    if message.text in district_map:

        slug = district_map[message.text]

        cursor.execute("DELETE FROM sent_links")
        db.commit()

        cursor.execute("UPDATE users SET district=?, active=1 WHERE user_id=?",
                       (slug, user_id))
        db.commit()

        cursor.execute("SELECT mode, rooms FROM users WHERE user_id=?", (user_id,))
        mode, rooms = cursor.fetchone()

        url = build_url(mode, rooms, slug)

        await message.answer("🔎 Отправляю первую страницу...\n")

        await send_results(user_id, url)
        return

# ================== ОТПРАВКА ==================

async def send_results(user_id, url):

    results = await parse(url)

    for title, price, link in results:

        cursor.execute("SELECT link FROM sent_links WHERE link=?", (link,))
        if cursor.fetchone():
            continue

        cursor.execute("INSERT INTO sent_links(link) VALUES(?)", (link,))
        db.commit()

        text = f"🏠 {title}\n💰 {price}\n🔗 {link}"

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

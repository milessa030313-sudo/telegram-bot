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

# ================= БАЗА =================
db = sqlite3.connect("database.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 1,
    mode TEXT,
    rooms TEXT,
    district TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_links(
    user_id INTEGER,
    link TEXT,
    PRIMARY KEY(user_id, link)
)
""")
db.commit()

# ================= КНОПКИ =================
mode_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🏠 Аренда"),
               KeyboardButton(text="🏡 Продажа")]],
    resize_keyboard=True
)

rooms_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="1️⃣ 1"), KeyboardButton(text="2️⃣ 2"), KeyboardButton(text="3️⃣ 3")],
        [KeyboardButton(text="4️⃣ 4"), KeyboardButton(text="5️⃣ 5+")],
        [KeyboardButton(text="⛔ Стоп")]
    ],
    resize_keyboard=True
)

district_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Алмалинский"), KeyboardButton(text="Ауэзовский")],
        [KeyboardButton(text="Бостандыкский"), KeyboardButton(text="Медеуский")],
        [KeyboardButton(text="Жетысуский"), KeyboardButton(text="Турксибский")],
        [KeyboardButton(text="Алатауский"), KeyboardButton(text="Наурызбайский")]
    ],
    resize_keyboard=True
)

district_map = {
    "Алмалинский": "almalinskij",
    "Ауэзовский": "aujezovskij",
    "Бостандыкский": "bostandykskij",
    "Жетысуский": "almaty-zhetysuskij",
    "Медеуский": "medeuskij",
    "Наурызбайский": "nauryzbajskiy",
    "Турксибский": "turksibskij",
    "Алатауский": "alatauskij"
}

# ================= URL =================
def build_url(mode, rooms, district):
    if mode == "rent":
        base = f"https://krisha.kz/arenda/kvartiry/almaty-{district}/"
    else:
        base = f"https://krisha.kz/prodazha/kvartiry/almaty-{district}/"
    return f"{base}?das[who]=1&das[live.rooms]={rooms}"

# ================= ПАРСЕР =================
async def parse(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=15) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.a-card")

    results = []
    for card in cards:
        title = card.select_one("a.a-card__title")
        price = card.select_one("div.a-card__price")
        if not title or not price:
            continue

        link = "https://krisha.kz" + title.get("href")
        results.append((title.text.strip(), price.text.strip(), link))

    return results

# ================= СТАРТ =================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Выберите режим:", reply_markup=mode_kb)

# ================= ОБРАБОТКА =================
@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id

    if message.text == "⛔ Стоп":
        cursor.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("❌ Автопоиск остановлен.")
        return

    if message.text in ["🏠 Аренда", "🏡 Продажа"]:
        mode = "rent" if message.text == "🏠 Аренда" else "sale"
        cursor.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        cursor.execute("UPDATE users SET mode=?, active=1 WHERE user_id=?", (mode, user_id))
        db.commit()
        await message.answer("Выберите количество комнат:", reply_markup=rooms_kb)
        return

    room_map = {
        "1️⃣ 1": "1",
        "2️⃣ 2": "2",
        "3️⃣ 3": "3",
        "4️⃣ 4": "4",
        "5️⃣ 5+": "5"
    }

    if message.text in room_map:
        cursor.execute("UPDATE users SET rooms=? WHERE user_id=?",
                       (room_map[message.text], user_id))
        db.commit()
        await message.answer("Выберите район:", reply_markup=district_kb)
        return

    if message.text in district_map:
        district = district_map[message.text]

        cursor.execute("UPDATE users SET district=?, active=1 WHERE user_id=?",
                       (district, user_id))
        cursor.execute("DELETE FROM sent_links WHERE user_id=?", (user_id,))
        db.commit()

        cursor.execute("SELECT mode, rooms FROM users WHERE user_id=?", (user_id,))
        mode, rooms = cursor.fetchone()

        url = build_url(mode, rooms, district)

        await message.answer("🔎 Отправляю первую страницу...\n")
        await send_results(user_id, url)
        return

# ================= ОТПРАВКА =================
async def send_results(user_id, url):
    results = await parse(url)

    for title, price, link in results:
        cursor.execute(
            "SELECT link FROM sent_links WHERE user_id=? AND link=?",
            (user_id, link)
        )
        if cursor.fetchone():
            continue

        cursor.execute(
            "INSERT INTO sent_links(user_id, link) VALUES(?, ?)",
            (user_id, link)
        )
        db.commit()

        await bot.send_message(user_id,
            f"🏠 {title}\n💰 {price}\n🔗 {link}"
        )

# ================= МОНИТОР =================
async def monitor():
    await asyncio.sleep(10)
    while True:
        cursor.execute("SELECT user_id, mode, rooms, district FROM users WHERE active=1")
        users = cursor.fetchall()

        for user_id, mode, rooms, district in users:
            if not district:
                continue
            url = build_url(mode, rooms, district)
            await send_results(user_id, url)

        await asyncio.sleep(120)

# ================= ЗАПУСК =================
async def main():
    print("🚀 Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(monitor())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

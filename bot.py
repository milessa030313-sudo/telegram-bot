import os
import asyncio
import sqlite3
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ================= БАЗА =================

db = sqlite3.connect("db.sqlite")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
district TEXT DEFAULT 'all'
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sent(
link TEXT
)
""")

db.commit()

# ================= МЕНЮ =================

main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(
    KeyboardButton("📍 Район"),
)

district_menu = ReplyKeyboardMarkup(resize_keyboard=True)
district_menu.add(
    KeyboardButton("Алмалинский"),
    KeyboardButton("Бостандыкский"),
)
district_menu.add(
    KeyboardButton("Все"),
    KeyboardButton("⬅ Назад")
)

# ================= START =================

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (message.from_user.id,))
    db.commit()
    await message.answer("Бот недвижимости запущен 🚀", reply_markup=main_menu)

# ================= ФИЛЬТР =================

@dp.message_handler(lambda message: message.text == "📍 Район")
async def district(message: types.Message):
    await message.answer("Выберите район:", reply_markup=district_menu)

@dp.message_handler(lambda message: message.text in ["Алмалинский","Бостандыкский","Все"])
async def save_district(message: types.Message):
    value = "all" if message.text == "Все" else message.text.lower()
    cur.execute("UPDATE users SET district=? WHERE id=?", (value, message.from_user.id))
    db.commit()
    await message.answer("Фильтр сохранён ✅", reply_markup=main_menu)

@dp.message_handler(lambda message: message.text == "⬅ Назад")
async def back(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu)

# ================= ПАРСЕР =================

def parse():
    url = "https://krisha.kz/arenda/kvartiry/almaty/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    cards = soup.select("div.a-card")

    results = []

    for card in cards[:5]:
        title = card.select_one("a.a-card__title").text.lower()
        link = "https://krisha.kz" + card.select_one("a.a-card__title")["href"]
        price = card.select_one("div.a-card__price").text.strip()
        address = card.select_one("div.a-card__subtitle")
        district = address.text.lower() if address else ""

        results.append((title, link, price, district))

    return results

# ================= МОНИТОР =================

async def monitor():
    await asyncio.sleep(10)
    while True:
        try:
            listings = parse()

            cur.execute("SELECT * FROM users")
            users = cur.fetchall()

            for title, link, price, district in listings:

                cur.execute("SELECT link FROM sent WHERE link=?", (link,))
                if cur.fetchone():
                    continue

                cur.execute("INSERT INTO sent VALUES(?)", (link,))
                db.commit()

                for user in users:
                    uid, user_district = user

                    if user_district != "all" and user_district not in district:
                        continue

                    await bot.send_message(
                        uid,
                        f"{title}\n💰 {price}\n🔗 {link}"
                    )

            await asyncio.sleep(300)

        except Exception as e:
            print("Ошибка:", e)
            await asyncio.sleep(60)

# ================= ЗАПУСК =================

async def on_startup(dp):
    asyncio.create_task(monitor())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

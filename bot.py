import asyncio
import sqlite3
import requests
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "ТВОЙ_ТОКЕН_СЮДА"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ================= БАЗА =================

db = sqlite3.connect("db.sqlite")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
seller_type TEXT DEFAULT 'all',
rooms TEXT DEFAULT 'all',
district TEXT DEFAULT 'all',
price_from INTEGER DEFAULT 0,
price_to INTEGER DEFAULT 999999999
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sent(
link TEXT
)
""")

db.commit()

# ================= FSM =================

class PriceState(StatesGroup):
    waiting_for_price_from = State()
    waiting_for_price_to = State()

# ================= МЕНЮ =================

def menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏠 Тип продавца", "🏢 Комнаты")
    kb.row("📍 Район", "💰 Цена")
    return kb

# ================= СТАРТ =================

@dp.message(CommandStart())
async def start(msg: Message):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (msg.from_user.id,))
    db.commit()
    await msg.answer("Бот запущен 🚀", reply_markup=menu())

# ================= ТИП ПРОДАВЦА =================

@dp.message(F.text == "🏠 Тип продавца")
async def seller_menu(msg: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Хозяин", "Агент")
    kb.row("Компания", "Все")
    await msg.answer("Выбери тип продавца:", reply_markup=kb)

@dp.message(F.text.in_(["Хозяин","Агент","Компания","Все"]))
async def save_seller(msg: Message):
    mapping = {
        "Хозяин":"owner",
        "Агент":"agent",
        "Компания":"company",
        "Все":"all"
    }
    cur.execute("UPDATE users SET seller_type=? WHERE id=?",
                (mapping[msg.text], msg.from_user.id))
    db.commit()
    await msg.answer("✅ Сохранено", reply_markup=menu())

# ================= КОМНАТЫ =================

@dp.message(F.text == "🏢 Комнаты")
async def rooms_menu(msg: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("1", "2", "3", "4+")
    kb.row("Все")
    await msg.answer("Выбери количество комнат:", reply_markup=kb)

@dp.message(F.text.in_(["1","2","3","4+","Все"]))
async def save_rooms(msg: Message):
    value = "4" if msg.text == "4+" else msg.text
    value = "all" if msg.text == "Все" else value
    cur.execute("UPDATE users SET rooms=? WHERE id=?",
                (value, msg.from_user.id))
    db.commit()
    await msg.answer("✅ Сохранено", reply_markup=menu())

# ================= РАЙОН =================

@dp.message(F.text == "📍 Район")
async def district_menu(msg: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Алмалинский","Бостандыкский")
    kb.row("Ауэзовский","Медеуский")
    kb.row("Все")
    await msg.answer("Выбери район:", reply_markup=kb)

@dp.message(F.text.in_(["Алмалинский","Бостандыкский",
                        "Ауэзовский","Медеуский","Все"]))
async def save_district(msg: Message):
    value = "all" if msg.text == "Все" else msg.text.lower()
    cur.execute("UPDATE users SET district=? WHERE id=?",
                (value, msg.from_user.id))
    db.commit()
    await msg.answer("✅ Сохранено", reply_markup=menu())

# ================= ЦЕНА =================

@dp.message(F.text == "💰 Цена")
async def price_start(msg: Message, state: FSMContext):
    await msg.answer("Напиши цену ОТ:")
    await state.set_state(PriceState.waiting_for_price_from)

@dp.message(PriceState.waiting_for_price_from)
async def save_price_from(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Введи число")
    await state.update_data(price_from=int(msg.text))
    await msg.
answer("Теперь напиши цену ДО:")
    await state.set_state(PriceState.waiting_for_price_to)

@dp.message(PriceState.waiting_for_price_to)
async def save_price_to(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Введи число")
    data = await state.get_data()
    price_from = data["price_from"]
    price_to = int(msg.text)

    cur.execute("""
    UPDATE users SET price_from=?, price_to=? WHERE id=?
    """, (price_from, price_to, msg.from_user.id))
    db.commit()

    await state.clear()
    await msg.answer("✅ Диапазон цены сохранён", reply_markup=menu())

# ================= ПАРСЕР =================

def parse():
    url = "https://krisha.kz/arenda/kvartiry/almaty/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text,"html.parser")

    card = soup.select_one("div.a-card")
    if not card:
        return None

    title = card.select_one("a.a-card__title").text.lower()
    link = "https://krisha.kz" + card.select_one("a.a-card__title")["href"]
    img = card.select_one("img")["src"]

    price_block = card.select_one("div.a-card__price")
    price = int(price_block.text.replace("₸","").replace(" ",""))

    address = card.select_one("div.a-card__subtitle")
    district = address.text.lower() if address else ""

    seller_block = card.select_one("div.a-card__owner")
    seller = seller_block.text.lower() if seller_block else ""

    rooms = "unknown"
    if "1-комн" in title: rooms="1"
    elif "2-комн" in title: rooms="2"
    elif "3-комн" in title: rooms="3"
    elif "4-комн" in title or "5-комн" in title: rooms="4"

    return title, link, img, seller, rooms, price, district

# ================= МОНИТОР =================

async def monitor():
    while True:
        data = parse()
        if not data:
            await asyncio.sleep(300)
            continue

        title, link, img, seller, rooms, price, district = data

        cur.execute("SELECT link FROM sent WHERE link=?", (link,))
        if cur.fetchone():
            await asyncio.sleep(300)
            continue

        cur.execute("INSERT INTO sent VALUES(?)",(link,))
        db.commit()

        cur.execute("SELECT * FROM users")
        users = cur.fetchall()

        for user in users:
            uid, seller_type, user_rooms, user_district, p_from, p_to = user

            if seller_type != "all":
                if seller_type == "owner" and "хозяин" not in seller: continue
                if seller_type == "agent" and "агент" not in seller: continue
                if seller_type == "company" and "компан" not in seller: continue

            if user_rooms != "all" and rooms != user_rooms:
                continue

            if user_district != "all" and user_district not in district:
                continue

            if not (p_from <= price <= p_to):
                continue

            await bot.send_photo(uid, img,
                caption=f"{title}\n\n💰 {price} ₸\n🔗 {link}")

        await asyncio.sleep(300)

# ================= ЗАПУСК =================

async def main():
    asyncio.create_task(monitor())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

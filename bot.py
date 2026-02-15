import asyncio
import os
import aiohttp
import sqlite3
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 7799445685
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== БАЗА ==================

db = sqlite3.connect("database.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 1,
    pro_until TEXT,
    trial_used INTEGER DEFAULT 0
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
        [KeyboardButton(text="🏠 Аренда")],
        [KeyboardButton(text="🏡 Продажа")],
        [KeyboardButton(text="🔴 Стоп"), KeyboardButton(text="🔵 Запустить")],
        [KeyboardButton(text="🎁 Бесплатно 2 часа")],
        [KeyboardButton(text="💎 Купить подписку")],
        [KeyboardButton(text="💳 Я оплатил")]
    ],
    resize_keyboard=True
)

# ================== ПАРСЕР ==================

async def parse(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
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
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (message.from_user.id,)
    )
    db.commit()

    await message.answer(
        "👋 Добро пожаловать!\n\nВыберите действие:",
        reply_markup=keyboard
    )

# ================== ОБРАБОТКА КНОПОК ==================

@dp.message()
async def handler(message: types.Message):

    user_id = message.from_user.id

    # 👇 СНАЧАЛА разрешаем служебные кнопки
    if message.text in ["🔴 Стоп", "🔵 Запустить", "🎁 Бесплатно 2 часа", "💎 Купить подписку", "💳 Я оплатил"]:
        pass
    else:
        # 👇 ПРОВЕРКА ПОДПИСКИ
        is_active = await check_subscription(user_id)

        if not is_active:
            await message.answer(
                "🔒 Доступ закрыт.\n\n"
                "🎁 Попробуйте бесплатно 2 часа\n"
                "или купите подписку."
            )
            return
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

    # РУЧНОЙ ЗАПРОС
    if message.text == "🏠 Аренда":
        await send_results(user_id, "https://krisha.kz/arenda/kvartiry/almaty/")

    if message.text == "🏡 Продажа":
        await send_results(user_id, "https://krisha.kz/prodazha/kvartiry/almaty/")
return

# ================= ОТПРАВКА =================

async def send_results(user_id, url):
    ads = await parse(url)
    for ad in ads:
        await bot.send_message(user_id, ad)

# ================= ОПЛАТА =================
    
@dp.message(lambda m: m.text == "💳 Я оплатил")
async def user_paid(message: types.Message):

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить оплату",
                callback_data=f"approve_{message.from_user.id}"
            )
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"💰 Новый платёж\nID: {message.from_user.id}",
        reply_markup=keyboard
    )

    await message.answer("⏳ Ожидайте подтверждения.")
@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_payment(callback: types.CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])
    expire = datetime.now() + timedelta(days=30)

    cursor.execute(
        "UPDATE users SET pro_until=? WHERE user_id=?",
        (expire.isoformat(), user_id)
    )
    db.commit()

    await bot.send_message(
        user_id,
        f"✅ Подписка активирована до {expire.strftime('%d.%m.%Y')}"
    )

    await callback.message.edit_text("✅ Подписка выдана.")
    
# ================== АВТОМОНИТОР ==================

async def monitor():
    await asyncio.sleep(10)

    while True:
        try:
            cursor.execute("SELECT user_id, pro_until FROM users WHERE active=1")
            users = cursor.fetchall()

for user_id, pro_until in users:

    # если нет подписки — пропускаем
    if not pro_until:
        continue

    expire = datetime.fromisoformat(pro_until)

    # если срок вышел — отключаем
    if expire < datetime.now():
        cursor.execute(
            "UPDATE users SET pro_until=NULL WHERE user_id=?",
            (user_id,)
        )
        db.commit()

        await bot.send_message(
            user_id,
            "❌ Ваша подписка закончилась.\n\n"
            "Продлите доступ для продолжения работы."
        )
        continue

    # если подписка активна — отправляем объявления
    await send_results(user_id, "https://krisha.kz/arenda/kvartiry/almaty/")

            await asyncio.sleep(120)  # 2 минуты

        except Exception as e:
            print("Ошибка:", e)
            await asyncio.sleep(60)

# ================== ЗАПУСК ==================

async def main():
    asyncio.create_task(monitor())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

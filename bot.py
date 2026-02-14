import asyncio
import os
import asyncpg
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db = None


# ===============================
# ТАРИФЫ
# ===============================

PLANS = {
    "START": {"price": 499000, "limit": 1},
    "BUSINESS": {"price": 999000, "limit": 3},
    "PRO": {"price": 1999000, "limit": 10},
}


# ===============================
# УТИЛИТЫ
# ===============================

def get_first_ad_id(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "lxml")

    first = soup.find("a", class_="a-card__title")
    if not first:
        return None

    link = "https://krisha.kz" + first.get("href")
    return link


async def get_user_plan(user_id):
    sub = await db.fetchrow("""
    SELECT plan, expires_at FROM subscriptions
    WHERE user_id=$1
    """, user_id)

    if not sub:
        return None

    if sub["expires_at"] < datetime.utcnow():
        return None

    return sub["plan"]


# ===============================
# START
# ===============================

@dp.message(Command("start"))
async def start(message: types.Message):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="💎 Купить подписку")],
            [types.KeyboardButton(text="➕ Добавить ссылку")],
            [types.KeyboardButton(text="📊 Мои ссылки")],
            [types.KeyboardButton(text="📅 Статус подписки")],
        ],
        resize_keyboard=True
    )

    await message.answer(
        "🏠 Krisha Monitor PRO\n\nДобавьте свою ссылку поиска и получайте уведомления.",
        reply_markup=keyboard
    )


# ===============================
# ПОКУПКА
# ===============================

@dp.message(F.text == "💎 Купить подписку")
async def show_plans(message: types.Message):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🟢 START")],
            [types.KeyboardButton(text="🟡 BUSINESS")],
            [types.KeyboardButton(text="🔴 PRO")],
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите тариф:", reply_markup=keyboard)


@dp.message(F.text.in_(["🟢 START", "🟡 BUSINESS", "🔴 PRO"]))
async def buy_plan(message: types.Message):

    plan = message.text.split()[1]
    price = PLANS[plan]["price"]

    prices = [LabeledPrice(label=f"{plan} 30 дней", amount=price)]

    await bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Krisha Monitor {plan}",
        description="Мониторинг ваших ссылок",
        payload=plan,
        provider_token=PROVIDER_TOKEN,
        currency="KZT",
        prices=prices,
    )


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):

    plan = message.successful_payment.invoice_payload
    expires = datetime.utcnow() + timedelta(days=30)

    await db.execute("""
    INSERT INTO subscriptions(user_id, plan, expires_at)
    VALUES($1, $2, $3)
    ON CONFLICT (user_id)
    DO UPDATE SET plan=$2, expires_at=$3
    """,
    message.from_user.id,
    plan,
    expires
    )

    await message.answer(
        f"✅ Подписка активирована\n"
        f"Тариф: {plan}\n"
        f"До: {expires.strftime('%d.%m.%Y')}"
    )


# ===============================
# ДОБАВЛЕНИЕ ССЫЛКИ
# ===============================

@dp.message(F.text == "➕ Добавить ссылку")
async def add_link(message: types.Message):

    plan = await get_user_plan(message.from_user.id)
    if not plan:
        await message.answer("❌ У вас нет активной подписки.")
        return

    await message.answer("Вставьте ссылку поиска Krisha:")


@dp.message(lambda m: m.text.startswith("https://krisha.kz"))
async def save_link(message: types.Message):

    plan = await get_user_plan(message.from_user.id)
    if not plan:
        return

    limit = PLANS[plan]["limit"]

    count = await db.fetchval("""
    SELECT COUNT(*) FROM links WHERE user_id=$1
    """, message.from_user.id)

    if count >= limit:
        await message.answer("❌ Достигнут лимит ссылок по вашему тарифу.")
        return

    first_id = get_first_ad_id(message.text)

    if not first_id:
        await message.answer("Не удалось обработать ссылку.")
        return

    await db.execute("""
    INSERT INTO links(user_id, url, last_seen_id)
    VALUES($1, $2, $3)
    """,
    message.from_user.id,
    message.text,
    first_id
    )

    await message.answer("✅ Ссылка добавлена.")


# ===============================
# МОИ ССЫЛКИ
# ===============================

@dp.message(F.text == "📊 Мои ссылки")
async def my_links(message: types.Message):

    rows = await db.fetch("""
    SELECT id, url FROM links WHERE user_id=$1
    """, message.from_user.id)

    if not rows:
        await message.answer("У вас нет ссылок.")
        return

    text = "Ваши ссылки:\n\n"
    for row in rows:
        text += f"{row['id']} — {row['url']}\n"

    await message.answer(text)


# ===============================
# СТАТУС
# ===============================

@dp.message(F.text == "📅 Статус подписки")
async def status(message: types.Message):

    sub = await db.fetchrow("""
    SELECT plan, expires_at FROM subscriptions
    WHERE user_id=$1
    """, message.from_user.id)

    if not sub:
        await message.answer("Подписка не активна.")
        return

    await message.answer(
        f"Тариф: {sub['plan']}\n"
        f"До: {sub['expires_at']}"
    )


# ===============================
# МОНИТОРИНГ
# ===============================

async def monitor():

    while True:

        users = await db.fetch("""
        SELECT user_id, plan FROM subscriptions
        WHERE expires_at > NOW()
        """)

        for user in users:

            links = await db.fetch("""
            SELECT id, url, last_seen_id FROM links
            WHERE user_id=$1
            """, user["user_id"])

            for link in links:

                new_id = get_first_ad_id(link["url"])

                if new_id and new_id != link["last_seen_id"]:

                    await db.execute("""
                    UPDATE links SET last_seen_id=$1 WHERE id=$2
                    """, new_id, link["id"])

                    try:
                        await bot.send_message(
                            user["user_id"],
                            f"🏠 Новое объявление:\n{new_id}"
                        )
                    except:
                        pass

        await asyncio.sleep(600)  # 10 минут


# ===============================
# MAIN
# ===============================

async def main():
    global db

    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        user_id BIGINT PRIMARY KEY,
        plan TEXT,
        expires_at TIMESTAMP
    )
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS links (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        url TEXT,
        last_seen_id TEXT
    )
    """)

    asyncio.create_task(monitor())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

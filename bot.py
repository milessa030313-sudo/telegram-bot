import asyncio
import os
import aiohttp
import asyncpg
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice

TOKEN = os.getenv("TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None

CHECK_INTERVAL = 30
SEND_DELAY = 0.05
MAX_PER_LOOP = 30

# ======================= БАЗА =======================

async def init_db():
    await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        tariff TEXT,
        expires_at TIMESTAMP
    )
    """)

async def set_subscription(user_id, tariff, days=30):
    expires = datetime.utcnow() + timedelta(days=days)
    await db.execute("""
    INSERT INTO users (user_id, tariff, expires_at)
    VALUES ($1, $2, $3)
    ON CONFLICT (user_id)
    DO UPDATE SET tariff=$2, expires_at=$3
    """, user_id, tariff, expires)

async def get_active_users():
    rows = await db.fetch("""
    SELECT user_id, tariff FROM users
    WHERE expires_at > NOW()
    """)
    return rows

async def get_user_status(user_id):
    row = await db.fetchrow("""
    SELECT tariff, expires_at FROM users
    WHERE user_id=$1
    """, user_id)
    return row

# ======================= ПАРСЕР =======================

async def parse_krisha(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="a-card__inc")

    results = []

    for card in cards[:8]:
        title_tag = card.find("a", class_="a-card__title")
        price_tag = card.find("div", class_="a-card__price")

        if not title_tag or not price_tag:
            continue

        title = title_tag.text.strip()
        price = price_tag.text.strip()
        link = "https://krisha.kz" + title_tag.get("href")

        results.append((title, price, link))

    return results

# ======================= АНТИСПАМ ОТПРАВКА =======================

async def safe_send(user_id, text):
    try:
        await bot.send_message(user_id, text)
        await asyncio.sleep(SEND_DELAY)
    except:
        pass

# ======================= АВТО-РАССЫЛКА =======================

sent_links = set()

async def auto_parser():
    global sent_links

    while True:
        print("🔄 Проверка объявлений...")

        users = await get_active_users()
        results = await parse_krisha(
            "https://krisha.kz/prodazha/kvartiry/almaty/"
        )

        counter = 0

        for title, price, link in results:
            if link not in sent_links:
                sent_links.add(link)

                text = f"""
🔥 Новое объявление

🏠 {title}
💰 {price}
🔗 {link}
"""

                for user in users:
                    await safe_send(user["user_id"], text)

                counter += 1
                if counter >= MAX_PER_LOOP:
                    break

        await asyncio.sleep(CHECK_INTERVAL)

# ======================= КОМАНДЫ =======================

@dp.message(Command("start"))
async def start(message: types.Message):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="💎 Купить Standard (1990₸)")],
            [types.KeyboardButton(text="👑 Купить Pro (3990₸)")],
            [types.KeyboardButton(text="📊 Мой статус")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Добро пожаловать в PRO-бот недвижимости.\nВыберите тариф:",
        reply_markup=keyboard
    )

# ======================= ОПЛАТА =======================

@dp.message(lambda m: "Standard" in m.text)
async def buy_standard(message: types.Message):

    prices = [LabeledPrice(label="Standard 30 дней", amount=199000)]

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Standard подписка",
        description="30 дней авто-уведомлений",
        payload="standard",
        provider_token=PROVIDER_TOKEN,
        currency="KZT",
        prices=prices,
        start_parameter="standard"
    )

@dp.message(lambda m: "Pro" in m.text)
async def buy_pro(message: types.Message):

    prices = [LabeledPrice(label="Pro 30 дней", amount=399000)]

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Pro подписка",
        description="Расширенные уведомления 30 дней",
        payload="pro",
        provider_token=PROVIDER_TOKEN,
        currency="KZT",
        prices=prices,
        start_parameter="pro"
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(lambda m: m.successful_payment)
async def successful_payment(message: types.Message):

    payload = message.successful_payment.invoice_payload

    if payload == "standard":
        await set_subscription(message.from_user.id, "standard")
    elif payload == "pro":
        await set_subscription(message.from_user.id, "pro")

    await message.answer("✅ Оплата успешна. Подписка активирована на 30 дней.")

# ======================= СТАТУС =======================

@dp.message(lambda m: m.text == "📊 Мой статус")
async def status(message: types.Message):

    data = await get_user_status(message.from_user.id)

    if not data:
        await message.answer("❌ Подписки нет.")
        return

    tariff = data["tariff"]
    expires = data["expires_at"]

    await message.answer(
        f"📊 Тариф: {tariff}\n⏳ Активна до: {expires.strftime('%d.%m.%Y %H:%M')}"
    )

# ======================= MAIN =======================

async def main():
    global db
    db = await asyncpg.connect(DATABASE_URL)
    await init_db()

    asyncio.create_task(auto_parser())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    

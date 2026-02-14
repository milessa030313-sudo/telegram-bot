import asyncio
import os
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice

TOKEN = os.getenv("TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

subscriptions = {}
sent_links = set()

CHECK_INTERVAL = 30

# ================= ПАРСЕР =================

async def parse_krisha(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="a-card__inc")

    results = []

    for card in cards[:5]:
        title_tag = card.find("a", class_="a-card__title")
        price_tag = card.find("div", class_="a-card__price")

        if not title_tag or not price_tag:
            continue

        title = title_tag.text.strip()
        price = price_tag.text.strip()
        link = "https://krisha.kz" + title_tag.get("href")

        results.append((title, price, link))

    return results


# ================= АВТО РАССЫЛКА =================

async def auto_parser():
    while True:
        now = datetime.now()

        for user_id, expiry in list(subscriptions.items()):

            if now > expiry:
                subscriptions.pop(user_id)
                continue

            results = await parse_krisha(
                "https://krisha.kz/prodazha/kvartiry/almaty/"
            )

            for title, price, link in results:
                if link not in sent_links:
                    sent_links.add(link)

                    text = f"""
🔥 Новое объявление

{title}
💰 {price}
🔗 {link}
"""
                    try:
                        await bot.send_message(user_id, text)
                        await asyncio.sleep(0.05)
                    except:
                        pass

        await asyncio.sleep(CHECK_INTERVAL)


# ================= START =================

@dp.message(Command("start"))
async def start(message: types.Message):

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="💎 Купить подписку")],
            [types.KeyboardButton(text="📊 Мой статус")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Добро пожаловать.\nДля авто-уведомлений нужна подписка.",
        reply_markup=keyboard
    )


# ================= КУПИТЬ =================

@dp.message(lambda m: m.text == "💎 Купить подписку")
async def buy(message: types.Message):

    prices = [LabeledPrice(label="Подписка 30 дней", amount=199000)]

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Premium подписка",
        description="Доступ к авто-уведомлениям 30 дней",
        payload="subscription",
        provider_token=PROVIDER_TOKEN,
        currency="KZT",
        prices=prices,
        start_parameter="subscribe"
    )


# ================= PRE CHECKOUT =================

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


# ================= УСПЕШНАЯ ОПЛАТА =================

@dp.message(lambda m: m.successful_payment)
async def successful_payment(message: types.Message):

    expiry_date = datetime.now() + timedelta(days=30)
    subscriptions[message.from_user.id] = expiry_date

    await message.answer(
        "✅ Оплата прошла успешно.\nПодписка активна 30 дней."
    )


# ================= СТАТУС =================

@dp.message(lambda m: m.text == "📊 Мой статус")
async def status(message: types.Message):

    expiry = subscriptions.get(message.from_user.id)

    if not expiry:
        await message.answer("❌ У вас нет активной подписки.")
    else:
        await message.answer(
            f"✅ Подписка активна до:\n{expiry.strftime('%d.%m.%Y %H:%M')}"
        )

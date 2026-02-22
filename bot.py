import asyncio
import os
import sqlite3
import time
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # ID админа для подтверждения платежей
PAYMENT_CARD = os.getenv("PAYMENT_CARD", "0000 0000 0000 0000")  # Карта для перевода
PAYMENT_AMOUNT = int(os.getenv("PAYMENT_AMOUNT", "7990"))  # Сумма подписки (₸)
TRIAL_MINUTES = 10

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= БАЗА =================
# Railway: используйте Volume и путь /data для сохранения БД
DB_PATH = os.getenv("DATABASE_PATH", "database.db")
db = sqlite3.connect(DB_PATH)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 1,
    mode TEXT,
    rooms TEXT,
    district TEXT,
    trial_started_at REAL,
    subscription_expires_at REAL,
    created_at REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_links(
    user_id INTEGER,
    link TEXT,
    PRIMARY KEY(user_id, link)
)
""")

# Миграции (если таблица была создана раньше без колонок)
try:
    cursor.execute("ALTER TABLE users ADD COLUMN trial_started_at REAL")
    db.commit()
except sqlite3.OperationalError:
    pass

try:
    cursor.execute("ALTER TABLE users ADD COLUMN subscription_expires_at REAL")
    db.commit()
except sqlite3.OperationalError:
    pass

try:
    cursor.execute("ALTER TABLE users ADD COLUMN created_at REAL")
    db.commit()
except sqlite3.OperationalError:
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS payment_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at REAL NOT NULL,
    confirmed_at REAL,
    confirmed_by INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
)
""")
db.commit()

# ================= ПРОВЕРКА ДОСТУПА =================
def has_access(user_id: int) -> tuple[bool, str]:
    """
    Проверяет доступ пользователя.
    Возвращает (доступ_есть, сообщение_если_нет).
    """
    cursor.execute(
        "SELECT trial_started_at, subscription_expires_at FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()
    now = time.time()
    if not row:
        return False, "Сначала нажмите /start"

    trial_started, sub_expires = row[0], row[1]

    # Платная подписка активна
    if sub_expires and sub_expires > now:
        return True, ""

    # Trial: 10 минут с первого запуска
    if trial_started:
        trial_end = trial_started + TRIAL_MINUTES * 60
        if now < trial_end:
            return True, ""
        amount_str = f"{PAYMENT_AMOUNT:,}".replace(",", " ")
        return False, (
            f"⏳ Бесплатный период (10 мин) закончился.\n\n"
            f"💳 Для продолжения оплатите подписку — {amount_str} ₸ на 30 дней.\n"
            f"Нажмите «💳 Оплатить» для получения реквизитов."
        )

    # Новый пользователь — даём trial
    cursor.execute(
        "UPDATE users SET trial_started_at=? WHERE user_id=?",
        (now, user_id)
    )
    db.commit()
    return True, ""

# ================= КНОПКИ =================
mode_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Аренда"), KeyboardButton(text="🏡 Продажа")],
        [KeyboardButton(text="💳 Оплатить")]
    ],
    resize_keyboard=True
)

rooms_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="1️⃣"), KeyboardButton(text="2️⃣"), KeyboardButton(text="3️⃣")],
        [KeyboardButton(text="4️⃣"), KeyboardButton(text="5️⃣+")],
        [KeyboardButton(text="⬅ Назад")]
    ],
    resize_keyboard=True
)

district_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Алмалинский"), KeyboardButton(text="Ауэзовский")],
        [KeyboardButton(text="Бостандыкский"), KeyboardButton(text="Медеуский")],
        [KeyboardButton(text="Жетысуский"), KeyboardButton(text="Турксибский")],
        [KeyboardButton(text="Алатауский"), KeyboardButton(text="Наурызбайский")],
        [KeyboardButton(text="⬅ Назад")]
    ],
    resize_keyboard=True
)

search_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚙ Изменить параметры")],
        [KeyboardButton(text="⛔ Стоп")]
    ],
    resize_keyboard=True
)

district_map = {
    "Алмалинский": "almalinskij",
    "Ауэзовский": "aujezovskij",
    "Бостандыкский": "bostandykskij",
    "Жетысуский": "zhetysuskij",
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
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
    db.commit()

    # фиксируем дату первого запуска (для статистики)
    now = time.time()
    cursor.execute(
        "UPDATE users SET created_at = COALESCE(created_at, ?) WHERE user_id=?",
        (now, user_id)
    )
    db.commit()

    access, msg = has_access(user_id)
    if access:
        await message.answer("Выберите режим:", reply_markup=mode_kb)
    else:
        await message.answer(msg, reply_markup=mode_kb)

# ================= СТАТИСТИКА (ТОЛЬКО АДМИН) =================
@dp.message(Command("stats"))
async def stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    now = time.time()
    day_ago = now - 24 * 3600
    week_ago = now - 7 * 24 * 3600

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM users WHERE created_at IS NOT NULL AND created_at >= ?", (day_ago,))
    today = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM users WHERE created_at IS NOT NULL AND created_at >= ?", (week_ago,))
    week = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_expires_at IS NOT NULL AND subscription_expires_at > ?", (now,))
    paid_active = cursor.fetchone()[0] or 0

    free = max(total - paid_active, 0)
    conversion = (paid_active / total * 100) if total else 0.0

    cursor.execute("""
        SELECT user_id, subscription_expires_at
        FROM users
        WHERE subscription_expires_at IS NOT NULL AND subscription_expires_at > ?
        ORDER BY subscription_expires_at ASC
    """, (now,))
    rows = cursor.fetchall()

    lines = []
    for uid, exp in rows:
        days_left = int((exp - now + 86399) // 86400)
        lines.append(f"👤 {uid} — {days_left} дн.")

    tail = "\n".join(lines) if lines else "—"

    await message.answer(
        "📊 Статистика бота\n\n"
        f"👥 Всего: {total}\n"
        f"📅 Сегодня: {today}\n"
        f"📈 За 7 дней: {week}\n\n"
        f"💎 Активные подписки: {paid_active}\n"
        f"🆓 Free: {free}\n"
        f"💰 Paid: {paid_active}\n"
        f"🔥 Конверсия: {conversion:.2f}%\n\n"
        "⏳ Осталось дней:\n"
        f"{tail}"
    )

# ================= ОПЛАТА =================
def pay_kb(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"pay:ok:{request_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pay:no:{request_id}"),
    )
    return builder.as_markup()

@dp.message(lambda m: m.text == "💳 Оплатить")
async def pay_info(message: types.Message):
    user_id = message.from_user.id
    access, msg = has_access(user_id)
    amount_str = f"{PAYMENT_AMOUNT:,}".replace(",", " ")

    kb = InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="✅ Оплатил", callback_data="pay:request")
    ).as_markup()

    if access:
        await message.answer(
            f"✅ У вас есть активный доступ.\n\n"
            f"Подписка: 30 дней — {amount_str} ₸\n"
            f"Реквизиты для перевода Kaspi:\n"
            f"💳 {PAYMENT_CARD}\n\n"
            f"После перевода нажмите «Оплатил» — администратор подтвердит платёж.",
            reply_markup=kb
        )
    else:
        await message.answer(
            f"💳 Подписка на 30 дней — {amount_str} ₸\n\n"
            f"Переведите на карту Kaspi:\n"
            f"💳 {PAYMENT_CARD}\n\n"
            f"После перевода нажмите «Оплатил» — администратор подтвердит платёж вручную.",
            reply_markup=kb
        )

@dp.callback_query(lambda c: c.data == "pay:request")
async def pay_request(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    now = time.time()

    cursor.execute(
        "INSERT INTO payment_requests(user_id, amount, created_at) VALUES(?, ?, ?)",
        (user_id, PAYMENT_AMOUNT, now)
    )
    db.commit()
    request_id = cursor.lastrowid

    user = callback.from_user
    username = user.username or "—"
    name = user.first_name or "—"

    await callback.answer("Заявка отправлена. Ожидайте подтверждения.")

    if ADMIN_ID:
        amount_str = f"{PAYMENT_AMOUNT:,}".replace(",", " ")
        await bot.send_message(
            ADMIN_ID,
            f"💳 Новая заявка на оплату #{request_id}\n\n"
            f"👤 User ID: {user_id}\n"
            f"📛 Имя: {name}\n"
            f"🔗 @{username}\n"
            f"💰 Сумма: {amount_str} ₸\n\n"
            f"Подтвердите после получения перевода:",
            reply_markup=pay_kb(request_id)
        )

    await callback.message.edit_text(
        "⏳ Заявка отправлена администратору.\n"
        "После подтверждения перевода вам придёт уведомление."
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("pay:ok:"))
async def pay_confirm(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[-1])
    now = time.time()
    expires = now + 30 * 24 * 3600

    cursor.execute(
        "SELECT user_id FROM payment_requests WHERE id=? AND status='pending'",
        (request_id,)
    )
    row = cursor.fetchone()
    if not row:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return

    user_id = row[0]

    cursor.execute(
        "UPDATE payment_requests SET status='confirmed', confirmed_at=?, confirmed_by=? WHERE id=?",
        (now, ADMIN_ID, request_id)
    )
    cursor.execute(
        "UPDATE users SET trial_started_at=NULL, subscription_expires_at=? WHERE user_id=?",
        (expires, user_id)
    )
    db.commit()

    await callback.answer("Платёж подтверждён.")
    await callback.message.edit_text(
        f"✅ Платёж #{request_id} подтверждён.\n"
        f"Пользователь {user_id} получил подписку на 30 дней."
    )

    try:
        await bot.send_message(
            user_id,
            f"✅ Платёж подтверждён!\n\n"
            f"Подписка активна до {datetime.fromtimestamp(expires).strftime('%d.%m.%Y')}.\n"
            f"Можете пользоваться поиском."
        )
    except Exception:
        pass

@dp.callback_query(lambda c: c.data and c.data.startswith("pay:no:"))
async def pay_reject(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[-1])

    cursor.execute(
        "SELECT user_id FROM payment_requests WHERE id=? AND status='pending'",
        (request_id,)
    )
    row = cursor.fetchone()
    if not row:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return

    user_id = row[0]
    cursor.execute("UPDATE payment_requests SET status='rejected' WHERE id=?", (request_id,))
    db.commit()

    await callback.answer("Заявка отклонена.")
    await callback.message.edit_text(f"❌ Заявка #{request_id} отклонена.")

    try:
        await bot.send_message(user_id, "❌ Платёж не подтверждён. Проверьте реквизиты и попробуйте снова.")
    except Exception:
        pass

# ================= ОБРАБОТКА =================
@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if text != "💳 Оплатить":
        access, msg = has_access(user_id)
        if not access:
            await message.answer(msg, reply_markup=mode_kb)
            return

    if text == "⛔ Стоп":
        cursor.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("❌ Автопоиск остановлен.", reply_markup=mode_kb)
        return

    if text == "⚙ Изменить параметры":
        cursor.execute("""
            UPDATE users
            SET active=0, mode=NULL, rooms=NULL, district=NULL
            WHERE user_id=?
        """, (user_id,))
        cursor.execute("DELETE FROM sent_links WHERE user_id=?", (user_id,))
        db.commit()
        await message.answer("🔄 Настройки сброшены.\nВыберите режим:", reply_markup=mode_kb)
        return

    if text == "⬅ Назад":
        cursor.execute("SELECT mode, rooms, district FROM users WHERE user_id=?", (user_id,))
        data = cursor.fetchone()
        if not data:
            await message.answer("Выберите режим:", reply_markup=mode_kb)
            return

        mode, rooms, district = data

        if district:
            cursor.execute("UPDATE users SET district=NULL WHERE user_id=?", (user_id,))
            db.commit()
            await message.answer("Выберите район:", reply_markup=district_kb)
            return

        if rooms:
            cursor.execute("UPDATE users SET rooms=NULL WHERE user_id=?", (user_id,))
            db.commit()
            await message.answer("Выберите количество комнат:", reply_markup=rooms_kb)
            return

        await message.answer("Выберите режим:", reply_markup=mode_kb)
        return

    if text in ["🏠 Аренда", "🏡 Продажа"]:
        mode = "rent" if text == "🏠 Аренда" else "sale"
        cursor.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        cursor.execute("UPDATE users SET mode=? WHERE user_id=?", (mode, user_id))
        db.commit()
        await message.answer("Выберите количество комнат:", reply_markup=rooms_kb)
        return

    room_map = {"1️⃣": "1", "2️⃣": "2", "3️⃣": "3", "4️⃣": "4", "5️⃣+": "5"}
    if text in room_map:
        cursor.execute("UPDATE users SET rooms=? WHERE user_id=?", (room_map[text], user_id))
        db.commit()
        await message.answer("Выберите район:", reply_markup=district_kb)
        return

    if text in district_map:
        district = district_map[text]
        cursor.execute("UPDATE users SET district=?, active=1 WHERE user_id=?", (district, user_id))
        cursor.execute("DELETE FROM sent_links WHERE user_id=?", (user_id,))
        db.commit()

        cursor.execute("SELECT mode, rooms FROM users WHERE user_id=?", (user_id,))
        mode, rooms = cursor.fetchone()

        url = build_url(mode, rooms, district)
        await message.answer("🔎 Отправляю текущие объявления (первая страница) \n\n" "⚡️Далее вы будете получать только новые варианты сразу после публикации", reply_markup=search_kb)
        await send_results(user_id, url)
        return

# ================= ОТПРАВКА =================
async def send_results(user_id, url):
    access, _ = has_access(user_id)
    if not access:
        return

    results = await parse(url)
    for title, price, link in results:
        cursor.execute("SELECT link FROM sent_links WHERE user_id=? AND link=?", (user_id, link))
        if cursor.fetchone():
            continue

        cursor.execute("INSERT INTO sent_links(user_id, link) VALUES(?, ?)", (user_id, link))
        db.commit()

        await bot.send_message(user_id, f"🏠 {title}\n💰 {price}\n🔗 {link}")

# ================= МОНИТОР =================
async def monitor():
    await asyncio.sleep(10)
    while True:
        cursor.execute("SELECT user_id, mode, rooms, district FROM users WHERE active=1")
        users = cursor.fetchall()

        for user_id, mode, rooms, district in users:
            if not district:
                continue

            access, _ = has_access(user_id)
            if not access:
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

from datetime import datetime, timedelta
import asyncio
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= ОТПРАВКА =================

async def send_results(user_id, url):
    ads = await parse(url)
    for ad in ads:
        await bot.send_message(user_id, ad)

# ================= ОПЛАТА =================

@dp.message(lambda m: m.text == "💳 Я оплатил")
async def user_paid(message: types.Message):

    user_id = message.from_user.id

    # создаём пользователя если его нет
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, active) VALUES (?, 1)",
        (user_id,)
    )
    db.commit()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить оплату",
                callback_data=f"approve_{user_id}"
            )
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"💰 Новый платёж\nID: {user_id}",
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
        "INSERT OR IGNORE INTO users (user_id, active) VALUES (?, 1)",
        (user_id,)
    )

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

# ================= БЕСПЛАТНО 2 ЧАСА =================

@dp.message(lambda m: m.text == "🎁 Бесплатно 2 часа")
async def free_trial(message: types.Message):

    user_id = message.from_user.id
    expire = datetime.now() + timedelta(hours=2)

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, active) VALUES (?, 1)",
        (user_id,)
    )

    cursor.execute(
        "UPDATE users SET pro_until=? WHERE user_id=?",
        (expire.isoformat(), user_id)
    )

    db.commit()

    await message.answer(
        f"✅ Бесплатный доступ активирован до {expire.strftime('%H:%M %d.%m.%Y')}"
    )

# ================= ПРОВЕРКА ДОСТУПА =================

async def has_access(user_id):

    cursor.execute(
        "SELECT pro_until FROM users WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if not result or not result[0]:
        return False

    expire = datetime.fromisoformat(result[0])

    if expire < datetime.now():
        return False

    return True

# ================== АВТОМОНИТОР ==================

async def monitor():
    while True:
        try:
            cursor.execute("SELECT user_id, pro_until FROM users WHERE active=1")
            users = cursor.fetchall()

            for user_id, pro_until in users:

                if not pro_until:
                    continue

                expire = datetime.fromisoformat(pro_until)

                if expire < datetime.now():
                    cursor.execute(
                        "UPDATE users SET pro_until=NULL WHERE user_id=?",
                        (user_id,)
                    )
                    db.commit()

                    await bot.send_message(
                        user_id,
                        "❌ Ваша подписка закончилась.\n\nПродлите доступ."
                    )
                    continue

                # если подписка активна — отправляем объявления
                await send_results(
                    user_id,
                    "https://krisha.kz/arenda/kvartiry/almaty/"
                )

        except Exception as e:
            print("Monitor error:", e)

        await asyncio.sleep(120)

# ================== ЗАПУСК ==================

async def main():
    asyncio.create_task(monitor())
    await dp.
    start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

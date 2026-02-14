import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Аренда")],
            [types.KeyboardButton(text="🏡 Продажа")],
            [types.KeyboardButton(text="🛒 Товары")]
        ],
        resize_keyboard=True
    )
    await message.answer("🚀 Бот запущен!\nВыберите категорию:", reply_markup=keyboard)


@dp.message()
async def handler(message: types.Message):
    await message.answer(f"Вы выбрали: {message.text}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

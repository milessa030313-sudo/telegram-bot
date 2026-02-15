import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Главное меню
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(
    KeyboardButton("🏠 Тип продавца"),
    KeyboardButton("🛏 Комнаты"),
)
main_menu.add(
    KeyboardButton("📍 Район"),
    KeyboardButton("💰 Цена"),
)

# Тип продавца
seller_menu = ReplyKeyboardMarkup(resize_keyboard=True)
seller_menu.add(
    KeyboardButton("Хозяин"),
    KeyboardButton("Агент"),
    KeyboardButton("Компания"),
)
seller_menu.add(KeyboardButton("⬅ Назад"))

# Комнаты
rooms_menu = ReplyKeyboardMarkup(resize_keyboard=True)
rooms_menu.add(
    KeyboardButton("1 комната"),
    KeyboardButton("2 комнаты"),
    KeyboardButton("3 комнаты"),
)
rooms_menu.add(KeyboardButton("⬅ Назад"))

# Районы
district_menu = ReplyKeyboardMarkup(resize_keyboard=True)
district_menu.add(
    KeyboardButton("Центр"),
    KeyboardButton("Север"),
    KeyboardButton("Юг"),
)
district_menu.add(KeyboardButton("⬅ Назад"))

# Цена
price_menu = ReplyKeyboardMarkup(resize_keyboard=True)
price_menu.add(
    KeyboardButton("До 5 млн"),
    KeyboardButton("5-10 млн"),
    KeyboardButton("10+ млн"),
)
price_menu.add(KeyboardButton("⬅ Назад"))


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Добро пожаловать в PRO-бот недвижимости 👋\nВыберите фильтр:", reply_markup=main_menu)


@dp.message_handler(lambda message: message.text == "🏠 Тип продавца")
async def seller(message: types.Message):
    await message.answer("Выберите тип продавца:", reply_markup=seller_menu)


@dp.message_handler(lambda message: message.text == "🛏 Комнаты")
async def rooms(message: types.Message):
    await message.answer("Выберите количество комнат:", reply_markup=rooms_menu)


@dp.message_handler(lambda message: message.text == "📍 Район")
async def district(message: types.Message):
    await message.answer("Выберите район:", reply_markup=district_menu)


@dp.message_handler(lambda message: message.text == "💰 Цена")
async def price(message: types.Message):
    await message.answer("Выберите диапазон цены:", reply_markup=price_menu)


@dp.message_handler(lambda message: message.text == "⬅ Назад")
async def back(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu)


@dp.message_handler()
async def filters(message: types.Message):
    await message.answer(f"Вы выбрали: {message.text}")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

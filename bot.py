else:
        await message.answer("🗑 Объявление удалено.")


# ======================
# MAIN
# ======================

async def main():
    global db

    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT
    )
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        category TEXT,
        description TEXT
    )
    """)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

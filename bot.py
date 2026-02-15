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

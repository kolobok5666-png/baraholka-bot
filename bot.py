import os
import json
import logging
from datetime import datetime


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)


load_dotenv = None
try:
    from dotenv import load_dotenv
except Exception:
    pass


if load_dotenv:
    load_dotenv()


TOKEN = os.getenv("TOKEN")
DATA_FILE = os.getenv("DATA_FILE", "/app/data/cars.json")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bot")


STATUS_LABELS = {
    1: "🟠 Приїхала / розбірка",
    2: "🔵 Малярка",
    3: "🔩 Збірка",
    4: "🟢 Готова / віддана",
}

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["➕ Нова машина"],
        ["🔍 Знайти машину"],
        ["🛠️ В роботі"],
        ["✅ Завершені"],
    ],
    resize_keyboard=True,
)

MAKES = {
    "Mazda": ["3", "6", "CX-5", "CX-7", "CX-9", "MX-5"],
    "Audi": ["A3", "A4", "A6", "A8", "Q3", "Q5", "Q7"],
    "Subaru": ["Impreza", "Legacy", "Forester", "Outback", "WRX"],
    "Fiat": ["500", "Punto", "Tipo", "Doblo", "Ducato"],
    "Mitsubishi": ["Lancer", "Outlander", "ASX", "Pajero", "Eclipse Cross"],
}


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE) or ".", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_cars(data, query):
    q = query.strip().lower()
    if not q:
        return []
    results = []
    for c in data:
        plate = str(c.get("plate", "")).lower()
        order = str(c.get("order", "")).lower()
        if q in plate or q in order:
            results.append(c)
    return results


def car_card(car):
    status = STATUS_LABELS.get(car.get("status", 1), "Невідомо")
    lines = []
    lines.append(f"🚘 <b>{car.get('model', 'Б/м')}</b>")
    lines.append(f"🔢 Номер авто: <code>{car.get('plate', '')}</code>")
    lines.append(f"🧾 Наряд: <code>{car.get('order', '')}</code>")
    lines.append(f"📌 Статус: {status}")
    parts_from = car.get("parts_from", "")
    if parts_from:
        lines.append(f"🔧 Запчастини від: {parts_from}")
    lines.append(f"📅 Створено: {car.get('created', '')}")
    notes = car.get("notes", [])
    if notes:
        lines.append("")
        lines.append("📝 <b>Примітки / роботи:</b>")
        for i, n in enumerate(notes, 1):
            lines.append(f"  {i}. {n}")
    return "\n".join(lines)


def car_buttons(car):
    st = car.get("status", 1)
    rows = []
    rows.append([InlineKeyboardButton("📝 Додати примітку", callback_data=f"note:{car['id']}")])
    rows.append([InlineKeyboardButton("🔄 Редагувати примітку", callback_data=f"editnote:{car['id']}")])
    rows.append([InlineKeyboardButton("🗑️ Видалити примітку", callback_data=f"delnote:{car['id']}")])
    rows.append([InlineKeyboardButton("🔧 Запчастини від авто", callback_data=f"parts:{car['id']}")])
    if st < 4:
        rows.append([InlineKeyboardButton(f"⬅️ Наступний етап ({st+1})", callback_data=f"stage:{car['id']}:{st+1}")])
    if st > 1:
        rows.append([InlineKeyboardButton(f"➡️ Попередній етап ({st-1})", callback_data=f"stage:{car['id']}:{st-1}")])
    rows.append([InlineKeyboardButton("🗑️ Видалити авто", callback_data=f"del:{car['id']}")])
    return InlineKeyboardMarkup(rows)


def make_keyboard(cars_ids, prefix):
    rows = []
    for cid in cars_ids:
        car = next((c for c in [] if False), None)
        rows.append([InlineKeyboardButton(f"№ {cid}", callback_data=f"{prefix}:{cid}")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт! Це бот обліку машин автосервісу.\n\n"
        "Оберіть дію кнопками нижче.",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if text == "➕ Нова машина":
        await cmd_new(update, context)
        return

    if text == "🔍 Знайти машину":
        context.user_data["mode"] = "search"
        await update.message.reply_text("🔍 Введіть номер авто або номер наряду:")
        return

    if text == "🛠️ В роботі":
        await show_by_status(update, context, in_progress=True)
        return

    if text == "✅ Завершені":
        await show_by_status(update, context, in_progress=False)
        return

    mode = context.user_data.get("mode")

    if mode == "search":
        data = load_data()
        results = find_cars(data, text)
        if not results:
            await update.message.reply_text("❌ Машину не знайдено.")
            return
        if len(results) == 1:
            await send_car_card(update, context, results[0])
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{c.get('plate')} / {c.get('order')}", callback_data=f"open:{c['id']}")]
                for c in results
            ])
            await update.message.reply_text("Знайдено декілька машин:", reply_markup=kb)
        context.user_data["mode"] = None
        return

    if mode == "new_plate":
        context.user_data["new"] = {"plate": text}
        context.user_data["mode"] = "new_order"
        await update.message.reply_text("🧾 Введіть номер наряду:")
        return

    if mode == "new_order":
        context.user_data["new"]["order"] = text
        context.user_data["mode"] = "new_make"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(m, callback_data=f"make:{m}")]
            for m in MAKES
        ] + [[InlineKeyboardButton("✍️ Своя марка", callback_data="make:custom")]])
        await update.message.reply_text("🚘 Оберіть марку:", reply_markup=kb)
        return

    if mode == "new_model":
        context.user_data["new"]["model"] = text
        context.user_data["mode"] = "new_parts"
        await update.message.reply_text(
            "🔧 Запчастини від якого авто? (напр. «VW Passat»)\n"
            "Напишіть текст або «—» щоб пропустити:"
        )
        return

    if mode == "new_parts":
        if text.strip() in ("—", "-"):
            context.user_data["new"]["parts_from"] = ""
        else:
            context.user_data["new"]["parts_from"] = text.strip()
        context.user_data["mode"] = None
        data = load_data()
        car = {
            "id": int(datetime.now().timestamp()),
            "plate": context.user_data["new"]["plate"],
            "order": context.user_data["new"]["order"],
            "model": context.user_data["new"]["model"],
            "status": 1,
            "notes": [],
            "parts_from": context.user_data["new"].get("parts_from", ""),
            "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        }
        data.append(car)
        save_data(data)
        await update.message.reply_text("✅ Машину додано!", reply_markup=MAIN_KEYBOARD)
        await send_car_card(update, context, car)
        return

    if mode == "note":
        car_id = context.user_data.get("car_id")
        data = load_data()
        car = next((c for c in data if c["id"] == car_id), None)
        if car:
            car["notes"].append(text)
            save_data(data)
            context.user_data["mode"] = None
            await update.message.reply_text("✅ Примітку додано!")
            await send_car_card(update, context, car)
        return

    if mode == "editnote":
        car_id = context.user_data.get("car_id")
        idx = context.user_data.get("note_idx")
        data = load_data()
        car = next((c for c in data if c["id"] == car_id), None)
        if car and 0 <= idx < len(car["notes"]):
            car["notes"][idx] = text
            save_data(data)
            context.user_data["mode"] = None
            await update.message.reply_text("✅ Примітку оновлено!")
            await send_car_card(update, context, car)
        return

    if mode == "parts":
        car_id = context.user_data.get("car_id")
        data = load_data()
        car = next((c for c in data if c["id"] == car_id), None)
        if car:
            car["parts_from"] = text.strip()
            save_data(data)
            context.user_data["mode"] = None
            await update.message.reply_text("✅ Запчастини оновлено!")
            await send_car_card(update, context, car)
        return

    await update.message.reply_text(
        "Оберіть дію кнопкою 👇",
        reply_markup=MAIN_KEYBOARD,
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "new_plate"
    await update.message.reply_text("🔢 Введіть номер авто (напр. АА1234ВЕ):")


async def send_car_card(update, context, car):
    await update.message.reply_text(
        car_card(car),
        reply_markup=car_buttons(car),
        parse_mode="HTML",
    )


async def show_by_status(update, context, in_progress):
    data = load_data()
    if in_progress:
        cars = [c for c in data if c.get("status", 1) < 4]
    else:
        cars = [c for c in data if c.get("status", 1) == 4]

    if not cars:
        await update.message.reply_text(
            "🛠️ Машин у роботі немає." if in_progress else "✅ Завершених машин немає."
        )
        return

    for car in cars:
        await update.message.reply_text(car_card(car), reply_markup=car_buttons(car), parse_mode="HTML")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data_store = load_data()

    if q.data.startswith("make:"):
        make = q.data.split(":", 1)[1]
        if make == "custom":
            context.user_data["mode"] = "new_make_text"
            await q.edit_message_text("✍️ Введіть назву марки вручну:")
            return
        models = MAKES.get(make, [])
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(m, callback_data=f"model:{make}:{m}")]
            for m in models
        ] + [[InlineKeyboardButton("✍️ Своя модель", callback_data=f"model:{make}:custom")]])
        await q.edit_message_text(f"🚗 {make} — оберіть модель:", reply_markup=kb)
        return

    if q.data.startswith("model:"):
        parts = q.data.split(":", 2)
        make = parts[1]
        model = parts[2]
        if model == "custom":
            context.user_data["mode"] = "new_model_text"
            context.user_data["make_sel"] = make
            await q.edit_message_text("✍️ Введіть назву моделі вручну:")
            return
        context.user_data["mode"] = "new_parts"
        context.user_data["new"]["model"] = f"{make} {model}"
        await q.edit_message_text(
            "🔧 Запчастини від якого авто? (напр. «VW Passat»)\n"
            "Напишіть текст або «—» щоб пропустити:"
        )
        return

    if q.data == "make:custom" or (q.data.startswith("model:") and q.data.endswith(":custom")):
        pass

    car_id = None

    if q.data.startswith("open:"):
        car_id = int(q.data.split(":")[1])
        car = next((c for c in data_store if c["id"] == car_id), None)
        if car:
            await q.edit_message_text(car_card(car), reply_markup=car_buttons(car), parse_mode="HTML")
        return

    if q.data.startswith("stage:"):
        parts = q.data.split(":")
        car_id = int(parts[1])
        new_stage = int(parts[2])
        car = next((c for c in data_store if c["id"] == car_id), None)
        if car:
            car["status"] = new_stage
            save_data(data_store)
            await q.edit_message_text(car_card(car), reply_markup=car_buttons(car), parse_mode="HTML")
        return

    if q.data.startswith("note:"):
        car_id = int(q.data.split(":")[1])
        context.user_data["mode"] = "note"
        context.user_data["car_id"] = car_id
        await q.edit_message_text("📝 Введіть примітку / роботи:")
        return

    if q.data.startswith("editnote:"):
        car_id = int(q.data.split(":")[1])
        car = next((c for c in data_store if c["id"] == car_id), None)
        if car and car.get("notes"):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(n, callback_data=f"picknote:{car_id}:{i}")]
                for i, n in enumerate(car["notes"])
            ])
            await q.edit_message_text("Оберіть примітку для редагування:", reply_markup=kb)
        else:
            await q.edit_message_text("Приміток поки немає.")
        return

    if q.data.startswith("picknote:"):
        parts = q.data.split(":")
        car_id = int(parts[1])
        idx = int(parts[2])
        context.user_data["mode"] = "editnote"
        context.user_data["car_id"] = car_id
        context.user_data["note_idx"] = idx
        await q.edit_message_text("✍️ Введіть новий текст примітки:")
        return

    if q.data.startswith("delnote:"):
        car_id = int(q.data.split(":")[1])
        car = next((c for c in data_store if c["id"] == car_id), None)
        if car:
            car["notes"] = []
            save_data(data_store)
            await q.edit_message_text("🗑️ Всі примітки видалено.")
        return

    if q.data.startswith("parts:"):
        car_id = int(q.data.split(":")[1])
        context.user_data["mode"] = "parts"
        context.user_data["car_id"] = car_id
        await q.edit_message_text("🔧 Запчастини від якого авто? (напр. «VW Passat»):")
        return

    if q.data.startswith("del:"):
        car_id = int(q.data.split(":")[1])
        data_store = [c for c in data_store if c["id"] != car_id]
        save_data(data_store)
        await q.edit_message_text("🗑️ Машину видалено.")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback))

    logger.info("Bot Niko starting...")
    app.run_polling()


if __name__ == "__main__":
    main()

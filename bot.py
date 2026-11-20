import os
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

load_dotenv()
TOKEN = os.getenv("TOKEN")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bot")

THREAD_TO_CATEGORY = {
    27: "одяг",
    7: "спорт",
    31: "хобі",
    32: "інше",
    25: "техніка",
    30: "ігри",
    26: "авто",
    6: "обмін",
    29: "інструменти",
    28: "дім",
    4: "куплю",
}

# Назви гілок основної групи як вони є в Telegram (будь-який регістр)
TOPIC_NAME_TO_CATEGORY = {
    "👕 одяг": "одяг",
    "🚲 спорт": "спорт",
    "🎨 хобі": "хобі",
    "📦 інше": "інше",
    "📱 техніка": "техніка",
    "🎮 ігри": "ігри",
    "🚗 авто": "авто",
    "🔄 обмін": "обмін",
    "🔧 інструменти": "інструменти",
    "🏠 дім": "дім",
    "🔎 куплю / шукаю": "куплю",
}

# Гілки, де бот не працює
IGNORED_TOPICS = ["правила", "спілкування"]

CATEGORY_LABELS = {
    "одяг": "👕 Одяг",
    "спорт": "🚲 Спорт",
    "хобі": "🎨 Хобі",
    "інше": "📦 Інше",
    "техніка": "📱 Техніка",
    "ігри": "🎮 Ігри",
    "авто": "🚗 Авто",
    "обмін": "🔄 Обмін",
    "інструменти": "🔧 Інструменти",
    "дім": "🏠 Дім",
    "куплю": "🔎 Куплю / шукаю",
}

REQUIRED_FIELDS = {
    "авто": ["title", "price", "city"],
    "техніка": ["title", "price", "city"],
    "одяг": ["title", "price", "city"],
    "аукціони": ["title", "price", "city"],
}

GENERIC_CATEGORIES = ["спорт", "хобі", "інше", "ігри", "обмін", "інструменти", "дім", "куплю"]
for _c in GENERIC_CATEGORIES:
    REQUIRED_FIELDS[_c] = ["title", "price", "city"]

OPTIONAL_FIELDS = {
    "авто": ["year", "engine", "mileage", "condition", "description", "delivery"],
    "техніка": ["specs", "condition", "description", "delivery"],
    "одяг": ["condition", "size", "description", "delivery"],
    "аукціони": ["condition", "description", "delivery"],
}
for _c in GENERIC_CATEGORIES:
    OPTIONAL_FIELDS[_c] = ["condition", "description", "delivery"]

FIELD_LABELS = {
    "title": "📦 Назва",
    "price": "💰 Ціна",
    "city": "📍 Місто",
    "condition": "📋 Стан",
    "delivery": "🚚 Доставка",
    "description": "📝 Опис",
    "size": "📏 Розмір",
    "year": "📅 Рік",
    "engine": "⚙️ Двигун",
    "mileage": "📊 Пробіг",
    "specs": "⚙️ Характеристики",
}

CITIES = [
    "київ", "харків", "одеса", "дніпро", "львів", "запоріжжя",
    "вінниця", "полтава", "суми", "житомир", "рівне", "тернопіль",
    "черкаси", "хмельницький", "чернівці", "ужгород", "івано-франківськ",
    "луцьк", "кропивницький", "херсон", "миколаїв", "чернігів",
]

BOT_USERNAME = None
BOT_USER_ID = None

# Cooldown: ліміт оголошень на користувача в гілці
COOLDOWN_LIMIT = 5
COOLDOWN_PERIOD = timedelta(days=1)


POST_TEMPLATES = {
    "одяг": [
        ("title", "👕"),
        ("condition", "📋 Стан"),
        ("size", "📏 Розмір"),
        ("description", "📝 Опис"),
        ("price", "💰 Ціна"),
        ("city", "📍 Місто"),
        ("delivery", "🚚 Доставка"),
        ("author", "👤 Продавець"),
        ("contact", "📩 Контакт"),
    ],
    "техніка": [
        ("title", "📱"),
        ("condition", "📋 Стан"),
        ("specs", "⚙️ Характеристики"),
        ("description", "📝 Опис"),
        ("price", "💰 Ціна"),
        ("city", "📍 Місто"),
        ("delivery", "🚚 Доставка"),
        ("author", "👤 Продавець"),
        ("contact", "📩 Контакт"),
    ],
    "авто": [
        ("title", "🚗"),
        ("year", "📅 Рік"),
        ("engine", "⚙️ Двигун"),
        ("mileage", "📊 Пробіг"),
        ("condition", "📋 Стан"),
        ("description", "📝 Опис"),
        ("price", "💰 Ціна"),
        ("city", "📍 Місто"),
        ("delivery", "🚚 Доставка"),
        ("author", "👤 Продавець"),
        ("contact", "📩 Контакт"),
    ],
    "аукціони": [
        ("title", "🔨"),
        ("condition", "📋 Стан"),
        ("description", "📝 Опис"),
        ("price", "💰 Ціна"),
        ("city", "📍 Місто"),
        ("delivery", "🚚 Доставка"),
        ("author", "👤 Продавець"),
        ("contact", "📩 Контакт"),
    ],
}

GENERIC_POST_TEMPLATE = [
    ("title", "📦"),
    ("condition", "📋 Стан"),
    ("description", "📝 Опис"),
    ("price", "💰 Ціна"),
    ("city", "📍 Місто"),
    ("delivery", "🚚 Доставка"),
    ("author", "👤 Продавець"),
    ("contact", "📩 Контакт"),
]
for _c in GENERIC_CATEGORIES:
    POST_TEMPLATES[_c] = list(GENERIC_POST_TEMPLATE)


def get_user_state(context):
    return context.user_data.get("state", {"phase": "idle", "data": {}, "photos": []})


def set_user_state(context, state):
    context.user_data["state"] = state


def parse_auto(text):
    d = {}
    low = text.lower()
    m = re.search(r"(\d{4})", text)
    if m:
        d["year"] = m.group(1)
    engines = ["1.0", "1.2", "1.4", "1.5", "1.6", "1.8", "2.0", "2.2", "2.4", "2.5", "3.0", "3.5", "4.0", "diesel", "бензин", "електро", "гібрид"]
    for e in engines:
        if e in low:
            d["engine"] = e
            break
    m = re.search(r"(\d[\d\s]*(?:тис|км|т\.?\s*км))", low)
    if m:
        d["mileage"] = m.group(0).strip()
    return d


def parse_price(text):
    """Parse price with currency detection. Returns dict with price and optionally currency."""
    low = text.lower()

    # USD patterns: 8900$, $8900, 8900 доларів, 8900 дол, 8900 USD
    usd_match = re.search(
        r"(\d[\d\s]*\d)\s*(?:\$|долар[іів]*|дол\.?\s*|usd)",
        low
    )
    if not usd_match:
        usd_match = re.search(r"\$\s*(\d[\d\s]*\d)", text)
    if usd_match:
        amount = usd_match.group(1).replace(" ", "")
        return {"price": f"{amount} $"}

    # EUR patterns: 2900€, €2900, 2900 євро, 2900 EUR
    eur_match = re.search(
        r"(\d[\d\s]*\d)\s*(?:€|євро|eur)",
        low
    )
    if not eur_match:
        eur_match = re.search(r"€\s*(\d[\d\s]*\d)", text)
    if eur_match:
        amount = eur_match.group(1).replace(" ", "")
        return {"price": f"{amount} €"}

    # UAH patterns: 2900₴, 2900 грн, 2900 UAH
    uah_match = re.search(
        r"(\d[\d\s]*\d)\s*(?:₴|грн|uah)",
        low
    )
    if not uah_match:
        uah_match = re.search(r"₴\s*(\d[\d\s]*\d)", text)
    if uah_match:
        amount = uah_match.group(1).replace(" ", "")
        return {"price": f"{amount} грн"}

    # Just a number with no currency indicator → don't set price, ask currency
    num_match = re.search(r"(\d[\d\s]*\d)", text)
    if num_match:
        return {"_raw_price": num_match.group(1).replace(" ", "")}

    return {}


def parse通用(text):
    d = {}

    price_info = parse_price(text)
    d.update(price_info)

    low = text.lower()

    if any(w in low for w in ["самовивіз", "сам", "забрати"]):
        d["delivery"] = "Самовивіз"
    elif any(w in low for w in ["доставка", "відправлю", "nova poshta", "нова пошта", "відправка"]):
        d["delivery"] = "Доставка"
    elif any(w in low for w in ["обидва", "і те і інше", "або"]):
        d["delivery"] = "Самовивіз або доставка"

    if any(w in low for w in ["новий", "нова", "нове", "запакований", "запакована"]):
        d["condition"] = "Новий"
    elif any(w in low for w in ["б/в", "вживаний", "вживана"]):
        d["condition"] = "Б/в"
    elif any(w in low for w in ["хорош", "норм", "відмінн"]):
        d["condition"] = "Стан хороший"

    for c in CITIES:
        if c in low:
            d["city"] = c.capitalize()
            break

    sizes = ["xs", "s", "m", "l", "xl", "xxl", "xxxl"]
    for s in sizes:
        if re.search(rf"\b{s}\b", low):
            d["size"] = s.upper()
            break

    return d


def extract_title(text):
    clean = text.strip()
    for pr in re.findall(r"\d[\d\s]*(?:грн|₴|\$|євро|€|долар|дол)", clean, re.IGNORECASE):
        clean = clean.replace(pr, "").strip()
    for word in ["ціна", "ціну", "можна", "торг", "продаю", "продам", "віддам"]:
        clean = clean.replace(word, "").strip()
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > 100:
        clean = clean[:100]
    return clean


def get_missing_fields(data, category):
    required = REQUIRED_FIELDS.get(category, [])
    missing = []
    for f in required:
        if not data.get(f):
            missing.append(f)
    return missing


def build_post(data, category):
    fields = POST_TEMPLATES.get(category, POST_TEMPLATES["техніка"])
    lines = ["🟢 <b>В НАЯВНОСТІ</b>\n"]
    title = data.get("title", "")
    for key, label in fields:
        if key == "title":
            if title:
                lines.append(f"{label} <b>{title}</b>\n")
            continue
        if key == "author":
            name = data.get("author_name", "")
            lines.append(f"{label}: {name}")
            continue
        if key == "contact":
            username = data.get("author_username", "")
            user_id = data.get("author_id", "")
            if username:
                lines.append(f"{label}: @{username}")
            elif user_id:
                link = f"tg://user?id={user_id}"
                lines.append(f"{label}: <a href=\"{link}\">Написати</a>")
            else:
                lines.append(f"{label}: Написати в особисті")
            continue
        val = data.get(key)
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def build_del_kb(ads):
    if not ads:
        return InlineKeyboardMarkup([])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🗑 {ad.get('title') or 'Оголошення'}", callback_data=f"del_pick:{i}")]
        for i, ad in enumerate(ads)
    ])


def action_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Опублікувати", callback_data="pub"),
            InlineKeyboardButton("❌ Скасувати", callback_data="cancel"),
        ],
        [InlineKeyboardButton("✏️ Редагувати", callback_data="edit_menu")],
        [InlineKeyboardButton("🗑 Видалити оголошення", callback_data="del")],
    ])


def currency_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("₴ Гривні", callback_data="cur:грн"),
            InlineKeyboardButton("$ Долари", callback_data="cur:$"),
            InlineKeyboardButton("€ Євро", callback_data="cur:€"),
        ],
    ])


def edit_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Назва", callback_data="ef:title")],
        [InlineKeyboardButton("📋 Стан", callback_data="ef:condition")],
        [InlineKeyboardButton("📝 Опис", callback_data="ef:description")],
        [InlineKeyboardButton("💰 Ціна", callback_data="ef:price")],
        [InlineKeyboardButton("📍 Місто", callback_data="ef:city")],
        [InlineKeyboardButton("🚚 Доставка", callback_data="ef:delivery")],
        [InlineKeyboardButton("📸 Фото", callback_data="ef:photo")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_draft")],
    ])


def edit_buttons_auto():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚗 Назва", callback_data="ef:title")],
        [InlineKeyboardButton("📅 Рік", callback_data="ef:year")],
        [InlineKeyboardButton("⚙️ Двигун", callback_data="ef:engine")],
        [InlineKeyboardButton("📊 Пробіг", callback_data="ef:mileage")],
        [InlineKeyboardButton("📋 Стан", callback_data="ef:condition")],
        [InlineKeyboardButton("📝 Опис", callback_data="ef:description")],
        [InlineKeyboardButton("💰 Ціна", callback_data="ef:price")],
        [InlineKeyboardButton("📍 Місто", callback_data="ef:city")],
        [InlineKeyboardButton("🚚 Доставка", callback_data="ef:delivery")],
        [InlineKeyboardButton("📸 Фото", callback_data="ef:photo")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_draft")],
    ])


def edit_buttons_clothes():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👕 Назва", callback_data="ef:title")],
        [InlineKeyboardButton("📋 Стан", callback_data="ef:condition")],
        [InlineKeyboardButton("📏 Розмір", callback_data="ef:size")],
        [InlineKeyboardButton("📝 Опис", callback_data="ef:description")],
        [InlineKeyboardButton("💰 Ціна", callback_data="ef:price")],
        [InlineKeyboardButton("📍 Місто", callback_data="ef:city")],
        [InlineKeyboardButton("🚚 Доставка", callback_data="ef:delivery")],
        [InlineKeyboardButton("📸 Фото", callback_data="ef:photo")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_draft")],
    ])


def get_edit_buttons(category):
    if category == "авто":
        return edit_buttons_auto()
    if category == "одяг":
        return edit_buttons_clothes()
    return edit_buttons()


FIELD_PROMPTS = {
    "title": "📝 Який товар продаєте?",
    "condition": "📋 Який стан?\nНовий / Б/в / Хороший",
    "description": "📝 Опишіть товар детальніше",
    "price": "💰 Яка ціна?",
    "city": "📍 Яке місто?",
    "delivery": "🚚 Яка доставка?\nСамовивіз / Доставка / Обидва",
    "size": "📏 Який розмір?",
    "year": "📅 Який рік випуску?",
    "engine": "⚙️ Який двигун?",
    "mileage": "📊 Який пробіг?",
    "specs": "⚙️ Які характеристики?",
}


async def analyze_and_respond(msg, state, context):
    data = state["data"]
    category = data.get("_cat", "техніка")

    if data.get("_raw_price"):
        raw = data.pop("_raw_price")
        state["_pending_price_num"] = raw
        set_user_state(context, state)
        await msg.reply_text(
            "💰 Яка валюта?",
            reply_markup=currency_buttons(),
        )
        return

    missing = get_missing_fields(data, category)
    if not state.get("photos"):
        missing.append("photo")
    if not missing:
        await show_draft(msg, state, context)
    else:
        labels = [FIELD_LABELS.get(f, "📸 Фото") for f in missing]
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустити", callback_data="skip_fields")]
        ])
        text = "👍 Оголошення майже готове!\n\nНе вистачає:\n"
        for l in labels:
            text += f"  {l}\n"
        text += "\nНапишіть ці дані або натисніть «Пропустити»."
        await msg.reply_text(text, reply_markup=skip_kb)


async def show_draft(msg, state, context):
    data = state["data"]
    category = data.get("_cat", "техніка")
    post_text = build_post(data, category)
    count = len(state.get("photos", []))

    header = "👀 <b>ПЕРЕВІРТЕ ОГОЛОШЕННЯ</b>\n\n"
    if count:
        header += f"📸 Фото: {count} шт.\n\n"

    state["phase"] = "draft"
    set_user_state(context, state)

    try:
        await msg.reply_text(
            header + post_text,
            reply_markup=action_buttons(),
            parse_mode="HTML",
        )
    except Exception as e:
        await msg.reply_text(f"⚠️ Помилка: {e}")


# ===================== HANDLERS =====================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type != "private":
        return

    user = msg.from_user
    args = context.args or []

    if args:
        raw = args[0]
        parts = raw.split("_")
        if len(parts) == 2:
            try:
                group_chat_id = int(parts[0])
                thread_id = int(parts[1])
            except ValueError:
                await msg.reply_text("❌ Помилка посилання.")
                return

            category = THREAD_TO_CATEGORY.get(thread_id)
            if not category:
                await msg.reply_text("❌ Гілка не знайдена.")
                return

            state = {
                "phase": "collect",
                "data": {
                    "_cat": category,
                    "_chat_id": group_chat_id,
                    "_thread_id": thread_id,
                    "author_id": user.id,
                    "author_name": user.full_name,
                    "author_username": user.username or "",
                },
                "photos": [],
            }
            set_user_state(context, state)

            cat_label = CATEGORY_LABELS.get(category, category)
            await msg.reply_text(
                f"✅ Гілка «{cat_label}» запам'ятована!\n\n"
                f"Надішліть інформацію про товар у зручний спосіб:\n"
                f"📸 Фото + 📝 текст\n"
                f"Або просто напишіть що продаєте."
            )
            return

    await msg.reply_text(
        "👋 Вітаю!\n\n"
        "Створіть оголошення, натиснувши «➕ Створити оголошення» "
        "в потрібній гілці групи."
    )


MAP_FILE = "thread_map.json"


def load_map():
    global THREAD_TO_CATEGORY
    try:
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            saved = {int(k): v for k, v in json.load(f).items()}
            THREAD_TO_CATEGORY.update(saved)
        logger.info("Loaded %d mapped topics", len(THREAD_TO_CATEGORY))
    except Exception as e:
        logger.warning("Could not load map: %s", e)


def save_map():
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(THREAD_TO_CATEGORY, f, ensure_ascii=False, indent=2)


ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Файли для статистики та адміна
ADMIN_FILE = os.getenv("ADMIN_FILE", "admin.json")
STATS_FILE = os.getenv("STATS_FILE", "stats.json")


def get_admin():
    if ADMIN_ID:
        return ADMIN_ID
    try:
        with open(ADMIN_FILE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("id", 0))
    except Exception:
        return 0


def set_admin(uid):
    with open(ADMIN_FILE, "w", encoding="utf-8") as f:
        json.dump({"id": uid}, f, ensure_ascii=False, indent=2)


def load_stats():
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def record_stat(uid, username, full_name, thread_id, category):
    stats = load_stats()
    stats.append({
        "uid": uid,
        "username": username,
        "full_name": full_name,
        "thread_id": thread_id,
        "category": category,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })
    save_stats(stats)


def build_stat_text(start_dt, end_dt):
    stats = load_stats()
    users = {}
    total = 0
    for e in stats:
        try:
            ts = datetime.fromisoformat(e["ts"])
        except Exception:
            continue
        if start_dt and ts < start_dt:
            continue
        if end_dt and ts > end_dt.replace(hour=23, minute=59, second=59):
            continue
        uid = e["uid"]
        u = users.setdefault(uid, {
            "name": e.get("full_name", ""),
            "username": e.get("username", ""),
            "count": 0,
            "dates": {},
            "cats": {},
        })
        u["count"] += 1
        d = ts.strftime("%d.%m.%Y")
        u["dates"][d] = u["dates"].get(d, 0) + 1
        cat = e.get("category", "?")
        u["cats"][cat] = u["cats"].get(cat, 0) + 1
        total += 1
    if not users:
        return "📭 За цей період оголошень не було."

    lines = [
        "📊 <b>Статистика оголошень</b>",
        f"Період: {start_dt.strftime('%d.%m.%Y')} – {end_dt.strftime('%d.%m.%Y')}" if start_dt and end_dt else "Весь період",
        f"Всього оголошень: {total} · Учасників: {len(users)}",
        "",
    ]
    for i, (uid, u) in enumerate(sorted(users.items(), key=lambda x: -x[1]["count"]), 1):
        who = f"@{u['username']}" if u["username"] else (u["name"] or f"id{uid}")
        lines.append(f"{i}) {who}")
        lines.append(f"   🗂 Оголошень: {u['count']}")
        dates = ", ".join(f"{d} ({n})" for d, n in sorted(u["dates"].items()))
        lines.append(f"   🗓 {dates}")
        cats = ", ".join(f"{CATEGORY_LABELS.get(c, c)} ({n})" for c, n in sorted(u["cats"].items(), key=lambda x: -x[1]))
        lines.append(f"   📂 {cats}")
        lines.append("")
    return "\n".join(lines)


def stat_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕒 Останні 7 днів", callback_data="stat:7d")],
        [InlineKeyboardButton("📆 Цей місяць", callback_data="stat:month")],
        [InlineKeyboardButton("🗓 Весь час", callback_data="stat:all")],
        [InlineKeyboardButton("📅 Свій період", callback_data="stat:custom")],
    ])


async def cmd_set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type != "private" or not msg.from_user:
        return
    user_id = msg.from_user.id
    args = context.args or []
    if len(args) != 1 or not args[0].isdigit():
        await msg.reply_text("Використання: /set_admin <id>\nПриклад: /set_admin 123456789")
        return
    new_id = int(args[0])
    current = get_admin()
    if current and user_id != current:
        await msg.reply_text("❌ Немає доступу.")
        return
    set_admin(new_id)
    await msg.reply_text(f"✅ Адміна встановлено: {new_id}")


async def cmd_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type != "private" or not msg.from_user:
        return
    admin_id = get_admin()
    if not admin_id or msg.from_user.id != admin_id:
        await msg.reply_text(
            "❌ Немає доступу.\n"
            "Введіть /set_admin <ваш_id> щоб стати адміном."
        )
        return
    await msg.reply_text("📊 Статистика оголошень.\nОберіть період:", reply_markup=stat_buttons())


async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or chat.type not in ("group", "supergroup"):
        return
    if not msg.new_chat_members:
        return
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=msg.message_id)
        logger.info("Deleted join message chat=%s msg=%s", chat.id, msg.message_id)
    except Exception as e:
        logger.warning("Could not delete join message: %s", e)


def parse_dates(text):
    found = re.findall(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if len(found) >= 2:
        try:
            d1 = datetime(int(found[0][2]), int(found[0][1]), int(found[0][0]))
            d2 = datetime(int(found[-1][2]), int(found[-1][1]), int(found[-1][0]))
            if d1 > d2:
                d1, d2 = d2, d1
            return d1, d2
        except ValueError:
            return None
    return None


async def cmd_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type != "private" or not msg.from_user:
        return
    user_id = msg.from_user.id
    admin_id = get_admin()
    if admin_id and user_id != admin_id:
        await msg.reply_text("❌ Немає доступу.")
        return
    parts = (context.args or [])
    if len(parts) == 2 and parts[0].isdigit() and parts[1] in CATEGORY_LABELS:
        THREAD_TO_CATEGORY[int(parts[0])] = parts[1]
        save_map()
        await msg.reply_text(
            f"✅ Гілку {parts[0]} → {CATEGORY_LABELS[parts[1]]} збережено."
        )
        return
    if len(parts) == 1 and parts[0] == "show":
        lines = "\n".join(
            f"{tid} → {CATEGORY_LABELS.get(c, c)}" for tid, c in sorted(THREAD_TO_CATEGORY.items())
        ) or "(порожньо)"
        await msg.reply_text(f"📋 Мапа гілок:\n{lines}")
        return
    if len(parts) == 1 and parts[0] == "clear":
        THREAD_TO_CATEGORY.clear()
        save_map()
        await msg.reply_text("🧹 Мапу очищено.")
        return
    cats = ", ".join(CATEGORY_LABELS.values())
    await msg.reply_text(
        "📋 Команди:\n"
        f"/map <thread_id> <категорія> — додати (категорії: {cats})\n"
        "/map show — показати\n"
        "/map clear — очистити"
    )


def topic_name_to_category(name):
    if not name:
        return None
    low = " ".join(name.lower().split())
    for ignored in IGNORED_TOPICS:
        if ignored in low:
            return None
    for key, cat in TOPIC_NAME_TO_CATEGORY.items():
        if key in low:
            return cat
    return None


async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if not msg or chat.type not in ("group", "supergroup"):
        return

    thread_id = getattr(msg, "message_thread_id", None)
    if not thread_id:
        return

    category = THREAD_TO_CATEGORY.get(thread_id)
    if not category:
        # Якщо мапа не заповнена — логуємо thread_id щоб адмін міг заповнити мапу
        logger.info("UNMAPPED_TOPIC chat=%s thread=%s text=%r",
                    chat.id, thread_id, (msg.text or "")[:30])
        return

    if msg.from_user and msg.from_user.id == BOT_USER_ID:
        return

    link = f"https://t.me/{BOT_USERNAME}?start={chat.id}_{thread_id}"

    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=msg.message_id)
    except Exception as e:
        logger.warning("Could not delete user message: %s", e)

    sent = await msg.chat.send_message(
        "🤖 Хочете продати товар?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Створити оголошення", url=link)],
            [InlineKeyboardButton("🗑 Видалити оголошення", callback_data="del")],
        ]),
        message_thread_id=thread_id,
    )
    state = get_user_state(context)
    state["_button_msg_id"] = sent.message_id
    state["_button_chat_id"] = chat.id
    set_user_state(context, state)

    async def auto_delete():
        await asyncio.sleep(10)
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=sent.message_id)
        except Exception:
            pass

    asyncio.create_task(auto_delete())


async def priv_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = msg.from_user
    if chat.type != "private" or not user:
        return

    state = get_user_state(context)

    if state["phase"] == "idle":
        await msg.reply_text(
            "Натисніть «➕ Створити оголошення» в гілці групи."
        )
        return

    if state["phase"] == "wait_field":
        field = state.get("waiting_field")
        if field and field != "photo":
            await msg.reply_text("📸 Надішліть саме фото.")
            return

    if state["phase"] == "draft":
        state["phase"] = "collect"

    photo = msg.photo[-1] if msg.photo else None
    if photo:
        state["photos"].append(photo.file_id)

    if msg.caption:
        parsed = parse通用(msg.caption)
        for k, v in parsed.items():
            if v and not state["data"].get(k):
                state["data"][k] = v
        title_from_cap = extract_title(msg.caption)
        if title_from_cap and not state["data"].get("title"):
            state["data"]["title"] = title_from_cap

    set_user_state(context, state)

    count = len(state["photos"])
    if count == 1:
        await msg.reply_text(f"📸 Фото додано.")
    await analyze_and_respond(msg, state, context)


async def priv_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = msg.from_user
    if chat.type != "private" or not user:
        return

    text = msg.text.strip()
    state = get_user_state(context)

    if context.user_data.get("stat_dates"):
        parsed = parse_dates(text)
        if not parsed:
            await msg.reply_text("❌ Не зрозумів дати. Формат: 01.01.2025 31.12.2025")
            return
        context.user_data.pop("stat_dates", None)
        d1, d2 = parsed
        await msg.reply_text(build_stat_text(d1, d2), parse_mode="HTML")
        return

    if text.lower() in ("/cancel", "скасувати", "стоп"):
        set_user_state(context, {"phase": "idle", "data": {}, "photos": []})
        await msg.reply_text("❌ Скасовано.")
        return

    if state["phase"] == "idle":
        await msg.reply_text(
            "Натисніть «➕ Створити оголошення» в гілці групи."
        )
        return

    if state["phase"] == "wait_field":
        field = state.get("waiting_field")
        if field == "photo":
            await msg.reply_text("📸 Надішліть саме фото.")
            return
        if field:
            state["data"][field] = text
            state["phase"] = "collect"
            state.pop("waiting_field", None)
            set_user_state(context, state)
            await analyze_and_respond(msg, state, context)
            return

    if state["phase"] == "draft":
        state["phase"] = "collect"

    if state["phase"] == "collect":
        parsed = parse通用(text)
        for k, v in parsed.items():
            if v and not state["data"].get(k):
                state["data"][k] = v

        if not state["data"].get("title"):
            title = extract_title(text)
            if title:
                state["data"]["title"] = title

        if state["data"].get("_cat") == "авто":
            auto = parse_auto(text)
            for k, v in auto.items():
                if v and not state["data"].get(k):
                    state["data"][k] = v

        set_user_state(context, state)
        await analyze_and_respond(msg, state, context)


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id
    state = get_user_state(context)

    logger.info("CALLBACK: user=%s data=%s phase=%s", uid, data, state.get("phase"))

    if data.startswith("stat:"):
        admin_id = get_admin()
        if not admin_id or q.from_user.id != admin_id:
            await q.edit_message_text("❌ Немає доступу.")
            return
        mode = data.split(":", 1)[1]
        now = datetime.now()
        if mode == "7d":
            start = now - timedelta(days=7)
            await q.edit_message_text(build_stat_text(start, now), parse_mode="HTML")
        elif mode == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            await q.edit_message_text(build_stat_text(start, now), parse_mode="HTML")
        elif mode == "all":
            await q.edit_message_text(build_stat_text(None, None), parse_mode="HTML")
        elif mode == "custom":
            context.user_data["stat_dates"] = True
            await q.edit_message_text(
                "📅 Введіть період двома датами (інтервалом).\n"
                "Приклад:\n"
                "01.01.2025 31.12.2025\n"
                "або 10.03.2025 – 15.03.2025"
            )
        else:
            await q.edit_message_text("❌ Невідома команда.")
        return

    if data.startswith("sel:"):
        tid = int(data.split(":")[1])
        category = THREAD_TO_CATEGORY.get(tid)
        if not category:
            await q.edit_message_text("❌ Гілка не знайдена.")
            return
        state["data"]["_cat"] = category
        state["data"]["_thread_id"] = tid
        state["phase"] = "collect"
        set_user_state(context, state)
        await q.edit_message_text(
            f"✅ Гілка «{CATEGORY_LABELS.get(category, category)}» запам'ятована!\n\n"
            f"Надішліть інформацію про товар:"
        )
        return

    if data.startswith("cur:"):
        currency = data.split(":")[1]
        raw_price = state.get("_pending_price_num", "")
        if raw_price:
            state["data"]["price"] = f"{raw_price} {currency}"
            state.pop("_pending_price_num", None)
            set_user_state(context, state)
            await analyze_and_respond(q.message, state, context)
        return

    if data == "skip_fields":
        missing = get_missing_fields(state["data"], state["data"].get("_cat", "техніка"))
        if missing:
            for f in missing:
                state["data"][f] = "Не вказано"
        set_user_state(context, state)
        await show_draft(q.message, state, context)
        return

    if data == "edit_menu":
        category = state["data"].get("_cat", "техніка")
        buttons = get_edit_buttons(category)
        await q.edit_message_text("✏️ Що змінити?", reply_markup=buttons)
        return

    if data.startswith("ef:"):
        field = data.split(":")[1]
        if field == "photo":
            state["phase"] = "collect"
            state.pop("waiting_field", None)
            set_user_state(context, state)
            await q.edit_message_text("📸 Надішліть нове фото:")
            return
        if field == "price":
            state["phase"] = "wait_field"
            state["waiting_field"] = "price"
            set_user_state(context, state)
            await q.edit_message_text(
                "💰 Введіть ціну з валютою\n(напр. 2900 грн, 100 $, 50 €):"
            )
            return
        prompt = FIELD_PROMPTS.get(field, f"Введіть «{field}»:")
        state["phase"] = "wait_field"
        state["waiting_field"] = field
        set_user_state(context, state)
        await q.edit_message_text(prompt)
        return

    if data == "back_to_draft":
        post_text = build_post(state["data"], state["data"].get("_cat", "техніка"))
        count = len(state.get("photos", []))
        header = "👀 <b>ПЕРЕВІРТЕ ОГОЛОШЕННЯ</b>\n\n"
        if count:
            header += f"📸 Фото: {count} шт.\n\n"
        state["phase"] = "draft"
        set_user_state(context, state)
        await q.edit_message_text(
            header + post_text,
            reply_markup=action_buttons(),
            parse_mode="HTML",
        )
        return

    if data == "pub":
        thread_id = state["data"].get("_thread_id")
        chat_id = state["data"].get("_chat_id")

        if not thread_id or not chat_id:
            await q.edit_message_text("❌ Невідома гілка. Натисніть «➕ Створити оголошення» знову.")
            return

        category = state["data"].get("_cat", "техніка")
        post_text = build_post(state["data"], category)
        photos = state.get("photos", [])

        ads_list = context.user_data.get("ads") or []
        published_now = 0
        now_dt = datetime.now()
        for a in ads_list:
            try:
                ts = datetime.fromisoformat(str(a.get("ts") or ""))
            except Exception:
                continue
            if (a.get("chat_id") == chat_id and a.get("thread_id") == thread_id
                    and now_dt - ts < COOLDOWN_PERIOD):
                published_now += 1

        if published_now >= COOLDOWN_LIMIT:
            await q.edit_message_text(
                f"⏳ Ви вже опублікували <b>{published_now}</b> оголошень у цій гілці за останні 24 години.\n"
                f"Обмеження: до <b>{COOLDOWN_LIMIT}</b> оголошень на користувача в гілці. Наразі нове оголошення не можна опублікувати."
            )
            return

        try:
            sent_msg = None
            if photos:
                if len(photos) == 1:
                    sent_msg = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photos[0],
                        caption=post_text,
                        parse_mode="HTML",
                        message_thread_id=thread_id,
                    )
                else:
                    media = [InputMediaPhoto(photos[0], caption=post_text, parse_mode="HTML")]
                    for p in photos[1:]:
                        media.append(InputMediaPhoto(p))
                    resp = await context.bot.send_media_group(
                        chat_id=chat_id,
                        media=media,
                        message_thread_id=thread_id,
                    )
                    sent_msg = resp[0] if isinstance(resp, (tuple, list)) and len(resp) > 0 else None
            else:
                sent_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=post_text,
                    parse_mode="HTML",
                    message_thread_id=thread_id,
                )
            sent_id = sent_msg.message_id if sent_msg else None
        except Exception as e:
            logger.error("PUBLISH ERROR: %s", e)
            await q.edit_message_text(f"⚠️ Помилка публікації: {e}")
            return

        context.user_data.setdefault("ads", []).append({
            "chat_id": chat_id,
            "thread_id": thread_id,
            "message_id": sent_id,
            "post_text": post_text,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "category": category,
        })

        await q.edit_message_text(
            "✅ Оголошення опубліковано!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 Видалити оголошення", callback_data="del")],
            ]),
        )

        record_stat(
            uid,
            state["data"].get("author_username", ""),
            state["data"].get("author_name", ""),
            thread_id,
            category,
        )

        button_msg_id = state.get("_button_msg_id")
        button_chat_id = state.get("_button_chat_id")
        if button_msg_id and button_chat_id:
            try:
                await context.bot.delete_message(chat_id=button_chat_id, message_id=button_msg_id)
            except Exception as e:
                logger.warning("Could not delete button message: %s", e)

        set_user_state(context, {"phase": "idle", "data": {}, "photos": []})
        logger.info("PUBLISHED: user=%s → chat=%s thread=%s", uid, chat_id, thread_id)
        return

    if data == "cancel":
        set_user_state(context, {"phase": "idle", "data": {}, "photos": []})
        await q.edit_message_text("❌ Скасовано.")
        return

    if data == "del":
        ads = context.user_data.get("ads") or []
        if not ads:
            await q.edit_message_text("🗑 У вас поки немає опублікованих оголошень.")
            return
        await q.edit_message_text(
            "🗑 <b>Оберіть оголошення для видалення</b>",
            reply_markup=build_del_kb(ads),
            parse_mode="HTML",
        )
        return

    if data.startswith("del_pick:"):
        try:
            idx = int(data.split(":", 1)[1])
        except Exception:
            await q.edit_message_text("❌ Помилка.")
            return
        ads = context.user_data.get("ads") or []
        if idx < 0 or idx >= len(ads):
            await q.edit_message_text("❌ Оголошення не знайдено.")
            return
        context.user_data["del_state"] = {"ads": ads, "idx": idx}
        ad = ads[idx]
        await q.edit_message_text(
            f"🗑 <b>Видалити це оголошення?</b>\n\n{ad.get('title') or 'Оголошення'}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Так", callback_data="del_yes")],
                [InlineKeyboardButton("❌ Ні", callback_data="del_no")],
            ]),
            parse_mode="HTML",
        )
        return

    if data == "del_yes" or data.startswith("del_yes:"):
        st = context.user_data.get("del_state") or {}
        ads = st.get("ads") or context.user_data.get("ads") or []
        idx = st.get("idx")
        ad = None
        if isinstance(idx, int) and 0 <= idx < len(ads):
            ad = ads[idx]
        if not ad:
            context.user_data.pop("del_state", None)
            await q.edit_message_text("❌ Оголошення не знайдено.")
            return
        deleted_ok = True
        try:
            await context.bot.delete_message(
                chat_id=ad.get("chat_id"),
                message_id=ad.get("message_id"),
                message_thread_id=ad.get("thread_id"),
            )
            logger.info("AD DELETED: user=%s chat=%s thread=%s msg=%s",
                        q.from_user.id, ad.get("chat_id"), ad.get("thread_id"), ad.get("message_id"))
        except Exception as e:
            deleted_ok = False
            logger.warning("AD DELETE ERROR: %s", e)
        if deleted_ok:
            user_ads = context.user_data.get("ads") or []
            context.user_data["ads"] = [
                a for a in user_ads
                if not (a.get("chat_id") == ad.get("chat_id")
                        and a.get("thread_id") == ad.get("thread_id")
                        and a.get("message_id") == ad.get("message_id"))
            ]
        context.user_data.pop("del_state", None)
        new_ads = context.user_data.get("ads") or []
        if new_ads:
            await q.edit_message_text(
                "🗑 <b>Оберіть оголошення для видалення</b>",
                reply_markup=build_del_kb(new_ads),
                parse_mode="HTML",
            )
        elif deleted_ok:
            await q.edit_message_text("✅ Оголошення видалено!")
        else:
            await q.edit_message_text("⚠️ Не вдалося видалити оголошення.")
        return

    if data == "del_no" or data.startswith("del_no:"):
        context.user_data.pop("del_state", None)
        ads = context.user_data.get("ads") or []
        if ads:
            await q.edit_message_text(
                "🗑 <b>Оберіть оголошення для видалення</b>",
                reply_markup=build_del_kb(ads),
                parse_mode="HTML",
            )
        else:
            await q.edit_message_text("📭 У вас поки немає опублікованих оголошень.")
        return


def main():
    global BOT_USERNAME, BOT_USER_ID

    async def on_startup(app):
        global BOT_USERNAME, BOT_USER_ID
        load_map()
        me = await app.bot.get_me()
        BOT_USERNAME = me.username
        BOT_USER_ID = me.id
        logger.info("Bot @%s (id=%s) started!", BOT_USERNAME, BOT_USER_ID)

    app = Application.builder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("map", cmd_map))
    app.add_handler(CommandHandler("set_admin", cmd_set_admin))
    app.add_handler(CommandHandler("stat", cmd_stat))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, priv_photo))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, priv_text))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, on_group_message))

    logger.info("Starting...")
    app.run_polling()


if __name__ == "__main__":
    main()

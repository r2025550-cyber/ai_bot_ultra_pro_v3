"""
Ultra-Pro Telegram AI Bot v3 (with AI Vision + Promotions + Scheduler + Panel + Stickers + GIFs + Roleplay + Admin Control + Sticker Grabber)
"""

import os
import json
import logging
import time
import random
from telebot import TeleBot, types
from utils.ai_helpers import AIHelper
from utils.db import Database
from utils.scheduler import SchedulerManager
from utils.panel import owner_panel_markup

# --- Helper: mask secrets for logs ---
def mask_secret(s: str, visible: int = 8):
    if not s:
        return "EMPTY"
    if len(s) <= visible:
        return s[0] + "*" * (len(s)-1)
    return s[:visible] + "..."

# --- Load config.json ---
CONFIG = {}
if os.path.exists("config.json"):
    try:
        with open("config.json", "r") as f:
            CONFIG = json.load(f) or {}
    except Exception as e:
        print("WARN >> failed to load config.json:", e)
        CONFIG = {}

# --- Load env vars ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or CONFIG.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or CONFIG.get("OPENAI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", str(CONFIG.get("OWNER_ID", "0")) or "0"))
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE") or CONFIG.get("DEFAULT_TIMEZONE", "Asia/Kolkata")

# --- Debug print ---
print("DEBUG >> TELEGRAM_TOKEN starts with:", mask_secret(TELEGRAM_TOKEN, 8))
print("DEBUG >> OPENAI_API_KEY starts with:", mask_secret(OPENAI_API_KEY, 8))
print("DEBUG >> OWNER_ID:", OWNER_ID)
print("DEBUG >> DEFAULT_TIMEZONE:", DEFAULT_TIMEZONE)

# --- Validate Telegram token ---
if not TELEGRAM_TOKEN or ":" not in TELEGRAM_TOKEN:
    raise ValueError(f"❌ TELEGRAM_TOKEN invalid or missing! Got: {mask_secret(TELEGRAM_TOKEN)}")

# --- Initialize bot ---
bot = TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Core helpers ---
db = Database("data/memory.db")
ai = None
if OPENAI_API_KEY:
    try:
        ai = AIHelper(openai_api_key=OPENAI_API_KEY)
        logger.info("AI helper initialized.")
    except Exception as e:
        ai = None
        logger.error(f"Failed to initialize AIHelper: {e}")

scheduler = SchedulerManager(bot, db, timezone=DEFAULT_TIMEZONE)

# --- Cooldown system ---
user_cooldowns = {}
COOLDOWN_SECONDS = 10  # increased to reduce spam

def can_reply(user_id: str) -> bool:
    now = time.time()
    last_time = user_cooldowns.get(user_id, 0)
    if now - last_time >= COOLDOWN_SECONDS:
        user_cooldowns[user_id] = now
        return True
    return False

# --- Should reply logic ---
def should_reply(msg: types.Message) -> bool:
    if msg.chat.type == "private":
        return True
    text = msg.text or ""
    entities = msg.entities or []
    bot_username = bot.get_me().username.lower()
    for ent in entities:
        if ent.type == "mention":
            mention = text[ent.offset:ent.offset+ent.length].lower()
            if bot_username not in mention:
                return False
    if f"@{bot_username}" in text.lower():
        return True
    return False

# =============== START ==================
@bot.message_handler(commands=["start"])
def start(msg: types.Message):
    db.add_group(msg.chat.id)
    markup = types.InlineKeyboardMarkup()
    bot_me = bot.get_me()
    if bot_me and bot_me.username:
        add_url = f"https://t.me/{bot_me.username}?startgroup=true"
        markup.add(types.InlineKeyboardButton("➕ Add me to your Group", url=add_url))
    markup.add(
        types.InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        types.InlineKeyboardButton("📊 Stats", callback_data="stats"),
        types.InlineKeyboardButton("⚡ Manage Admins", callback_data="manage_admins"),
        types.InlineKeyboardButton("📋 Sticker Grabber", callback_data="sticker_grabber")
    )
    markup.add(types.InlineKeyboardButton("💬 Support", url="https://t.me/your_support_channel"))
    bot.reply_to(msg, "🤖 Ultra-Pro AI Bot v3 ready!\nUse /panel for owner controls.", reply_markup=markup)

# =============== OWNER PANEL ==================
@bot.message_handler(commands=["panel"])
def panel(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Not allowed.")
    markup = owner_panel_markup()
    markup.add(types.InlineKeyboardButton("⚡ Manage Admins", callback_data="manage_admins"))
    markup.add(types.InlineKeyboardButton("📋 Sticker Grabber", callback_data="sticker_grabber"))
    bot.send_message(OWNER_ID, "⚙️ Owner Panel", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: True)
def cb(call: types.CallbackQuery):
    if call.from_user.id != OWNER_ID:
        return bot.answer_callback_query(call.id, "❌ Not allowed")
    try:
        if call.data == "list_groups":
            groups = db.get_groups()
            bot.send_message(OWNER_ID, "📋 Groups:\n" + ("\n".join(map(str, groups)) if groups else "None"))
        elif call.data == "new_schedule":
            bot.send_message(OWNER_ID, "📝 Use /schedule YYYY-MM-DD HH:MM <None/daily/weekly/monthly> Message")
        elif call.data == "instant_broadcast":
            bot.send_message(OWNER_ID, "🚀 Use /broadcast or /broadcast_media")
        elif call.data == "cancel_schedules":
            scheduler.cancel_all()
            db.clear_schedules()
            bot.send_message(OWNER_ID, "✅ All schedules cleared.")
        elif call.data == "help":
            bot.send_message(OWNER_ID, "ℹ️ Help: Use /broadcast, /schedule, /panel for controls.")
        elif call.data == "stats":
            g = len(db.get_groups()); u = db.count_users(); s = len(db.list_schedules())
            bot.send_message(OWNER_ID, f"📊 Stats\nGroups:{g}\nUsers:{u}\nSchedules:{s}")
        elif call.data == "manage_admins":
            try:
                admins = bot.get_chat_administrators(call.message.chat.id)
                admin_list = "\n".join([f"👤 {a.user.first_name}" for a in admins])
                bot.send_message(OWNER_ID, f"⚡ Current Admins:\n{admin_list}")
            except Exception as e:
                bot.send_message(OWNER_ID, f"⚠️ Failed to fetch admins: {e}")
        elif call.data == "sticker_grabber":
            bot.send_message(OWNER_ID, "🖼️ Reply to any sticker with /grabsticker to fetch its file_id.")
    except Exception as e:
        logger.error("Callback handler error: %s", e)
        bot.answer_callback_query(call.id, "⚠️ Error processing action.")

# =============== STICKER GRABBER ==================
@bot.message_handler(commands=["grabsticker"])
def grab_sticker(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Not allowed.")
    if not msg.reply_to_message or not msg.reply_to_message.sticker:
        return bot.reply_to(msg, "⚠️ Reply to a sticker with this command to grab its file_id.")
    sticker_id = msg.reply_to_message.sticker.file_id
    bot.reply_to(msg, f"✅ Sticker file_id:\n<code>{sticker_id}</code>", parse_mode="HTML")

# =============== AI CHAT ==================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def chat(msg):
    if not should_reply(msg):
        return
    try:
        db.add_group(msg.chat.id)
        uid = str(msg.from_user.id)
        if not can_reply(uid):
            return
        db.add_memory(uid, "user", msg.text)
        mem = db.get_memory(uid, limit=6)
        if not ai:
            return bot.send_message(msg.chat.id, "⚠️ AI not configured.")
        try:
            reply = ai.chat_reply(f"As a friendly girl named Butki, reply playfully: {msg.text}", mem)
        except Exception as e:
            logger.error(f"AI error: {e}")
            reply = "⚠️ Sorry, abhi thoda busy hoon 💖"
        db.add_memory(uid, "assistant", reply)
        bot.send_message(msg.chat.id, reply)
    except Exception as e:
        logger.exception("Chat error:")
        bot.reply_to(msg, "⚠️ Error, please try again later.")

# =============== STICKERS ==================
STICKER_IDS = [
    "CAACAgUAAxkBAAMsaM0_Bknmh1kNnNzEH8GpllJ3HIUAAhsRAAJV8BFUGQQlAfumZL02BA",
    "CAACAgEAAxkBAAMoaM03EtaeDFGFrsRC0MDNSM8LgbIAAu4AAyAK8EYrQPDMf_R-rDYE",
    "CAACAgUAAxkBAAMmaM03DTk-hY3KvaMEPcsK548XFvsAApAUAALFL-BVvNXMv2XTJPg2BA",
    "CAACAgUAAyEFAAStbkSDAAIBzmjNJBx_mcgcx3KBYU1O9dpWegpPAAI7FQACbMwgVFrPF5hMaq5UNgQ",
    "CAACAgUAAxkBAANNaM1VMX0VXi_2ql897hzgwKnlkGQAAjsOAAIKCDlW81YQdhOWt402BA",
    "CAACAgUAAxkBAANNaM1VMX0VXi_2ql897hzgwKnlkGQAAjsOAAIKCDlW81YQdhOWt402BA",
]

@bot.message_handler(content_types=["sticker"])
def sticker(msg: types.Message):
    emoji = msg.sticker.emoji if msg.sticker else "🙂"
    try:
        if ai and can_reply(str(msg.from_user.id)) and random.random() < 0.5:
            prompt = f"Ek ladki Butki ki tarah roleplay karo. User ne {emoji} sticker bheja hai."
            reply = ai.chat_reply(prompt)
            bot.reply_to(msg, reply)
        else:
            if STICKER_IDS:
                sticker_id = random.choice(STICKER_IDS)
                bot.send_sticker(msg.chat.id, sticker_id, reply_to_message_id=msg.message_id)
            else:
                bot.reply_to(msg, f"{emoji} Cute sticker!")
    except Exception as e:
        logger.error(f"Sticker reply error: {e}")
        bot.reply_to(msg, f"{emoji} (sticker received)")

# =============== GIF ==================
@bot.message_handler(content_types=["animation"])
def gif(msg: types.Message):
    bot.reply_to(msg, "😂🔥 Cool GIF!")

# =============== RESTORE SCHEDULES ==================
try:
    scheduler.restore_jobs_from_db()
except Exception as e:
    logger.error("Failed to restore scheduler jobs: %s", e)

# =============== RUN ==================
if __name__ == "__main__":
    print("Bot running v3...")
    backoff = 1
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=20)
        except Exception as e:
            logger.exception(f"⚠️ Polling crashed: {e}, restarting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

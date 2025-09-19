"""
Ultra-Pro Telegram AI Bot v3 (with AI Vision + Promotions + Scheduler + Panel + Stickers + GIFs + Roleplay)
"""

import os
import json
import logging
import time
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
    return s[:visible] + "..."  # do not print full key

# --- Load config.json (optional fallback, DO NOT overwrite environment variables) ---
CONFIG = {}
if os.path.exists("config.json"):
    try:
        with open("config.json", "r") as f:
            CONFIG = json.load(f) or {}
    except Exception as e:
        print("WARN >> failed to load config.json:", e)
        CONFIG = {}

# --- Load env vars (prefer environment, fallback to config.json) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or CONFIG.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or CONFIG.get("OPENAI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", str(CONFIG.get("OWNER_ID", "0")) or "0"))
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE") or CONFIG.get("DEFAULT_TIMEZONE", "Asia/Kolkata")

# --- Debug print for Railway / deployment logs (masked) ---
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

# --- AI helper ---
ai = None
if OPENAI_API_KEY and isinstance(OPENAI_API_KEY, str) and OPENAI_API_KEY.strip():
    try:
        ai = AIHelper(openai_api_key=OPENAI_API_KEY)
        logger.info("AI helper initialized.")
    except Exception as e:
        ai = None
        logger.error(f"Failed to initialize AIHelper: {e}")
else:
    logger.warning("OPENAI_API_KEY not configured. AI features will be disabled.")

scheduler = SchedulerManager(bot, db, timezone=DEFAULT_TIMEZONE)

# --- Cooldown system (user_id -> last_reply_time) ---
user_cooldowns = {}
COOLDOWN_SECONDS = 5

def can_reply(user_id: str) -> bool:
    now = time.time()
    last_time = user_cooldowns.get(user_id, 0)
    if now - last_time >= COOLDOWN_SECONDS:
        user_cooldowns[user_id] = now
        return True
    return False

# =============== START + BUTTONS ==================
@bot.message_handler(commands=["start"])
def start(msg: types.Message):
    db.add_group(msg.chat.id)
    markup = types.InlineKeyboardMarkup()
    try:
        bot_me = bot.get_me()
        username = getattr(bot_me, "username", None)
    except Exception:
        username = None
    if username:
        add_url = f"https://t.me/{username}?startgroup=true"
        markup.add(types.InlineKeyboardButton("➕ Add me to your Group", url=add_url))
    else:
        markup.add(types.InlineKeyboardButton("➕ Add to group (open bot)", url="https://t.me/your_bot_username"))

    markup.add(
        types.InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        types.InlineKeyboardButton("📊 Stats", callback_data="stats")
    )
    markup.add(types.InlineKeyboardButton("💬 Support", url="https://t.me/your_support_channel"))
    bot.reply_to(msg, "🤖 Ultra-Pro AI Bot v3 ready!\nUse /panel for owner controls.", reply_markup=markup)

# =============== OWNER PANEL ==================
@bot.message_handler(commands=["panel"])
def panel(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Not allowed.")
    bot.send_message(OWNER_ID, "⚙️ Owner Panel", reply_markup=owner_panel_markup())

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
    except Exception as e:
        logger.error("Callback handler error: %s", e)
        bot.answer_callback_query(call.id, "⚠️ Error processing action.")

# =============== BROADCAST ==================
@bot.message_handler(commands=["broadcast"])
def broadcast(msg):
    if msg.from_user.id != OWNER_ID:
        return
    text = msg.text.replace("/broadcast", "").strip()
    for gid in db.get_groups():
        try:
            bot.send_message(gid, f"📢 {text}")
        except Exception as e:
            logger.error(f"Broadcast error to {gid}: {e}")
    bot.reply_to(msg, "✅ Broadcast sent.")

@bot.message_handler(commands=["broadcast_media"])
def broadcast_media(msg):
    if msg.from_user.id != OWNER_ID:
        return
    if not msg.reply_to_message:
        return bot.reply_to(msg, "Reply to media with /broadcast_media")
    r = msg.reply_to_message
    for gid in db.get_groups():
        try:
            if r.photo:
                bot.send_photo(gid, r.photo[-1].file_id, caption=r.caption or "")
            elif r.video:
                bot.send_video(gid, r.video.file_id, caption=r.caption or "")
            elif r.document:
                bot.send_document(gid, r.document.file_id, caption=r.caption or "")
        except Exception as e:
            logger.error(f"Broadcast media error to {gid}: {e}")
    bot.reply_to(msg, "✅ Media broadcast sent.")

# =============== SCHEDULER ==================
@bot.message_handler(commands=["schedule"])
def schedule(msg):
    if msg.from_user.id != OWNER_ID:
        return
    parts = msg.text.split(" ", 4)
    if len(parts) < 4 and not msg.reply_to_message:
        return bot.reply_to(msg, "Usage: /schedule YYYY-MM-DD HH:MM <recurring> message")
    _, d, t, r = parts[:4]
    payload = parts[4] if len(parts) > 4 else ""
    media = None
    if msg.reply_to_message:
        rm = msg.reply_to_message
        if rm.photo:
            media = rm.photo[-1].file_id
        elif rm.video:
            media = rm.video.file_id
        elif rm.document:
            media = rm.document.file_id
        if not payload:
            payload = rm.caption or ""
    run_time = f"{d} {t}"
    jobid = scheduler.schedule_broadcast(run_time, payload, media, r)
    db.add_schedule(jobid, payload, media, run_time, r)
    bot.reply_to(msg, f"✅ Scheduled {run_time} recurring={r}")

# =============== AI CHAT ==================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def chat(msg):
    try:
        db.add_group(msg.chat.id)
        uid = str(msg.from_user.id)

        if not can_reply(uid):
            return  # skip if cooldown not passed

        db.add_memory(uid, "user", msg.text)
        mem = db.get_memory(uid, limit=6)

        if not ai:
            bot.send_message(msg.chat.id, "⚠️ AI is not configured. Please contact the bot owner.")
            return

        reply = ai.chat_reply(msg.text, mem)
        db.add_memory(uid, "assistant", reply)
        bot.send_message(msg.chat.id, reply)
    except Exception as e:
        logger.exception("Chat error:")
        bot.reply_to(msg, "⚠️ AI error, please try again later.")

# =============== IMAGE, STICKER, GIF ==================
@bot.message_handler(content_types=["photo"])
def photo(msg: types.Message):
    uid = str(msg.from_user.id)
    caption = msg.caption or ""
    if caption:
        mem = db.get_memory(uid, limit=5)
        if not ai:
            bot.reply_to(msg, "⚠️ AI/image features not configured.")
            return
        reply = ai.chat_reply(caption, mem)
        bot.reply_to(msg, reply)
    else:
        try:
            file_info = bot.get_file(msg.photo[-1].file_id)
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
            if not ai:
                bot.reply_to(msg, "🖼️ Uploaded — image analysis not configured.")
                return
            vision_reply = ai.vision_describe(file_url)
            bot.reply_to(msg, f"🖼️ {vision_reply}")
        except Exception as e:
            logger.error(f"Vision error: {e}")
            bot.reply_to(msg, "🖼️ Nice picture!")

@bot.message_handler(content_types=["sticker"])
def sticker(msg: types.Message):
    emoji = msg.sticker.emoji if msg.sticker else "🙂"
    try:
        if ai and can_reply(str(msg.from_user.id)):
            reply = ai.chat_reply(f"User sent a {emoji} sticker. Reply playfully like roleplay.")
            bot.reply_to(msg, reply)
        else:
            bot.reply_to(msg, f"{emoji} Nice sticker!")
    except Exception as e:
        logger.error(f"Sticker reply error: {e}")
        bot.reply_to(msg, f"{emoji} (sticker received)")

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

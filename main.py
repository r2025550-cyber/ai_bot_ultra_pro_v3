"""
Ultra-Pro Telegram AI Bot v3 (with AI Vision + Promotions + Scheduler + Panel + Stickers + GIFs)
"""

import os, json, logging
from telebot import TeleBot, types
import openai
from utils.db import Database
from utils.ai_helpers import AIHelper
from utils.scheduler import SchedulerManager
from utils.panel import owner_panel_markup

# --- Load env vars (Railway/Render style) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")

# --- Debug print for Railway Logs ---
print("DEBUG >> TELEGRAM_TOKEN starts with:", TELEGRAM_TOKEN[:8] if TELEGRAM_TOKEN else "EMPTY")
if not TELEGRAM_TOKEN or ":" not in TELEGRAM_TOKEN:
    raise ValueError(f"❌ TELEGRAM_TOKEN invalid! Got: {TELEGRAM_TOKEN}")

# --- Initialize bot ---
bot = TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")
openai.api_key = OPENAI_API_KEY

# --- Setup logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Init Helpers ---
db = Database("data/memory.db")
ai = AIHelper(openai_api_key=OPENAI_API_KEY)
scheduler = SchedulerManager(bot, db, timezone=DEFAULT_TIMEZONE)

# --- Owner Commands (panel, broadcast, schedule) ---
@bot.message_handler(commands=["start"])
def start(msg: types.Message):
    db.add_group(msg.chat.id)
    bot.reply_to(msg, "🤖 Ultra-Pro AI Bot v3 ready! Use /panel for owner controls.")

@bot.message_handler(commands=["panel"])
def panel(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Not allowed.")
    bot.send_message(OWNER_ID, "⚙️ Owner Panel", reply_markup=owner_panel_markup())

@bot.callback_query_handler(func=lambda c: True)
def cb(call: types.CallbackQuery):
    if call.from_user.id != OWNER_ID:
        return bot.answer_callback_query(call.id, "❌ Not allowed")
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

@bot.message_handler(commands=["broadcast"])
def broadcast(msg):
    if msg.from_user.id != OWNER_ID:
        return
    text = msg.text.replace("/broadcast", "").strip()
    for gid in db.get_groups():
        try:
            bot.send_message(gid, f"📢 {text}")
        except:
            continue
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
        except:
            continue
    bot.reply_to(msg, "✅ Media broadcast sent.")

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

@bot.message_handler(commands=["stats"])
def stats(msg):
    if msg.from_user.id != OWNER_ID:
        return
    g = len(db.get_groups())
    u = db.count_users()
    s = len(db.list_schedules())
    bot.reply_to(msg, f"📊 Stats\nGroups:{g}\nUsers:{u}\nSchedules:{s}")

# --- AI Chat ---
@bot.message_handler(func=lambda m: True, content_types=["text"])
def chat(msg):
    db.add_group(msg.chat.id)
    uid = str(msg.from_user.id)
    db.add_memory(uid, "user", msg.text)
    mem = db.get_memory(uid, limit=6)
    reply = ai.chat_reply(msg.text, mem)
    db.add_memory(uid, "assistant", reply)
    bot.send_message(msg.chat.id, reply)

# --- Image, Sticker, GIF ---
@bot.message_handler(content_types=["photo"])
def photo(msg: types.Message):
    uid = str(msg.from_user.id)
    caption = msg.caption or ""
    if caption:
        db.add_memory(uid, "user", caption)
        mem = db.get_memory(uid, limit=5)
        reply = ai.chat_reply(caption, mem)
        db.add_memory(uid, "assistant", reply)
        bot.reply_to(msg, reply)
    else:
        file_info = bot.get_file(msg.photo[-1].file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
        try:
            vision_reply = ai.vision_describe(file_url)
            bot.reply_to(msg, f"🖼️ {vision_reply}")
        except Exception:
            bot.reply_to(msg, "🖼️ Nice picture!")

@bot.message_handler(content_types=["sticker"])
def sticker(msg: types.Message):
    emoji = msg.sticker.emoji if msg.sticker else "🙂"
    bot.reply_to(msg, f"{emoji} Nice sticker!")

@bot.message_handler(content_types=["animation"])
def gif(msg: types.Message):
    bot.reply_to(msg, "😂🔥 Cool GIF!")

# --- Restore scheduled jobs ---
scheduler.restore_jobs_from_db()

if __name__ == "__main__":
    print("Bot running v3...")
    bot.infinity_polling()

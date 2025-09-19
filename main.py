"""
Ultra-Pro Telegram AI Bot v4
(with AI Vision + Promotions + Scheduler + Panel + Stickers + GIFs + Advanced Buttons)
"""

import os, json, logging
from telebot import TeleBot, types
from openai import OpenAI

# --- Load env vars ---
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

# --- Load config.json if present ---
if os.path.exists("config.json"):
    with open("config.json","r") as f:
        CONFIG = json.load(f)
    TELEGRAM_TOKEN = CONFIG.get("TELEGRAM_TOKEN", TELEGRAM_TOKEN)
    OPENAI_API_KEY = CONFIG.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OWNER_ID = int(CONFIG.get("OWNER_ID", OWNER_ID))
    DEFAULT_TIMEZONE = CONFIG.get("DEFAULT_TIMEZONE", DEFAULT_TIMEZONE)

bot = TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy Database + Scheduler (replace with real)
class Database:
    def __init__(self, path): self.groups=set(); self.users=set()
    def add_group(self, gid): self.groups.add(gid)
    def get_groups(self): return list(self.groups)
    def add_memory(self, uid, role, text): pass
    def get_memory(self, uid, limit=5): return []
    def count_users(self): return len(self.users)
    def list_schedules(self): return []
    def add_schedule(self,*a): pass
    def clear_schedules(self): pass

class SchedulerManager:
    def __init__(self, bot, db, timezone): pass
    def cancel_all(self): pass
    def restore_jobs_from_db(self): pass
    def schedule_broadcast(self, run_time, payload, media, r): return "job123"

db = Database("data/memory.db")
scheduler = SchedulerManager(bot, db, timezone=DEFAULT_TIMEZONE)

# --- AI Helper ---
class AIHelper:
    def __init__(self, client): self.client = client

    def chat_reply(self, user_message, memory=None):
        context = ""
        if memory:
            for role, content in memory:
                context += f"{role}: {content}\n"
        prompt = f"{context}\nUser: {user_message}\nAssistant:"

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful Telegram AI assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()

    def vision_describe(self, image_url):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe this image"},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ]
        )
        return response.choices[0].message.content.strip()

ai = AIHelper(openai_client)

# --- Start Command with Buttons ---
@bot.message_handler(commands=["start"])
def start(msg: types.Message):
    db.add_group(msg.chat.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ Add Me To Your Group", url=f"https://t.me/{bot.get_me().username}?startgroup=true"))
    kb.add(types.InlineKeyboardButton("👤 Profile", callback_data="profile"),
           types.InlineKeyboardButton("ℹ️ Help", callback_data="help"))
    if msg.from_user.id == OWNER_ID:
        kb.add(types.InlineKeyboardButton("⚙️ Owner Panel", callback_data="owner_panel"))
    bot.reply_to(msg, "🤖 Ultra-Pro AI Bot v4 ready! Choose an option below:", reply_markup=kb)

# --- Callback Buttons ---
@bot.callback_query_handler(func=lambda c: True)
def cb(call: types.CallbackQuery):
    if call.data == "profile":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"👤 Your Profile\nID: {call.from_user.id}\nName: {call.from_user.first_name}")
    elif call.data == "help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "ℹ️ Use me to chat with AI, generate image captions, schedule broadcasts, and more!")
    elif call.data == "owner_panel":
        if call.from_user.id != OWNER_ID:
            return bot.answer_callback_query(call.id, "❌ Not allowed")
        panel(call.message)

# --- Owner Panel ---
def owner_panel_markup():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 Groups", callback_data="list_groups"))
    kb.add(types.InlineKeyboardButton("📝 New Schedule", callback_data="new_schedule"))
    kb.add(types.InlineKeyboardButton("🚀 Instant Broadcast", callback_data="instant_broadcast"))
    kb.add(types.InlineKeyboardButton("❌ Cancel All", callback_data="cancel_schedules"))
    return kb

@bot.message_handler(commands=["panel"])
def panel(msg: types.Message):
    if msg.from_user.id!=OWNER_ID:
        return bot.reply_to(msg,"❌ Not allowed.")
    bot.send_message(OWNER_ID,"⚙️ Owner Panel",reply_markup=owner_panel_markup())

# --- Broadcast Commands ---
@bot.message_handler(commands=["broadcast"])
def broadcast(msg):
    if msg.from_user.id!=OWNER_ID: return
    text=msg.text.replace("/broadcast","").strip()
    for gid in db.get_groups():
        try: bot.send_message(gid,f"📢 {text}")
        except: continue
    bot.reply_to(msg,"✅ Broadcast sent.")

@bot.message_handler(commands=["broadcast_media"])
def broadcast_media(msg):
    if msg.from_user.id!=OWNER_ID: return
    if not msg.reply_to_message: return bot.reply_to(msg,"Reply to media with /broadcast_media")
    r=msg.reply_to_message
    for gid in db.get_groups():
        try:
            if r.photo: bot.send_photo(gid,r.photo[-1].file_id,caption=r.caption or "")
            elif r.video: bot.send_video(gid,r.video.file_id,caption=r.caption or "")
            elif r.document: bot.send_document(gid,r.document.file_id,caption=r.caption or "")
        except: continue
    bot.reply_to(msg,"✅ Media broadcast sent.")

# --- AI Chat ---
@bot.message_handler(func=lambda m: True,content_types=["text"])
def chat(msg):
    db.add_group(msg.chat.id)
    uid=str(msg.from_user.id)
    db.add_memory(uid,"user",msg.text)
    mem=db.get_memory(uid,limit=6)
    reply=ai.chat_reply(msg.text,mem)
    db.add_memory(uid,"assistant",reply)
    bot.send_message(msg.chat.id,reply)

# --- Image, Sticker, GIF ---
@bot.message_handler(content_types=["photo"])
def photo(msg: types.Message):
    file_info = bot.get_file(msg.photo[-1].file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
    try:
        vision_reply=ai.vision_describe(file_url)
        bot.reply_to(msg,f"🖼️ {vision_reply}")
    except Exception:
        bot.reply_to(msg,"🖼️ Nice picture!")

@bot.message_handler(content_types=["sticker"])
def sticker(msg: types.Message):
    emoji=msg.sticker.emoji if msg.sticker else "🙂"
    bot.reply_to(msg,f"{emoji} Nice sticker!")

@bot.message_handler(content_types=["animation"])
def gif(msg: types.Message):
    bot.reply_to(msg,"😂🔥 Cool GIF!")

# --- Run Bot ---
scheduler.restore_jobs_from_db()

if __name__=="__main__":
    print("Bot running v4...")
    bot.infinity_polling()

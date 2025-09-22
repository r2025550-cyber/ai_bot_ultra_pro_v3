# main.py
"""
Ultra-Pro Telegram AI Bot v3
(with AI Vision + Promotions + Scheduler + Panel + Stickers + GIFs
+ Roleplay + Admin Control + Sticker Grabber + Broadcast Manager)
"""

import os
import json
import logging
import time
import random
from typing import Optional
from telebot import TeleBot, types
from utils.ai_helpers import AIHelper
from utils.db import Database
from utils.scheduler import SchedulerManager
from utils.panel import owner_panel_markup

# --- Helper: mask secrets for logs ---
def mask_secret(s: Optional[str], visible: int = 8):
    if not s:
        return "EMPTY"
    s = str(s)
    if len(s) <= visible:
        return s[0] + "*" * (len(s)-1)
    return s[:visible] + "..."

# --- Ensure data directory ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

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
db = Database(os.path.join(DATA_DIR, "memory.db"))
ai = None
if OPENAI_API_KEY:
    try:
        ai = AIHelper(openai_api_key=OPENAI_API_KEY)
        logger.info("AI helper initialized.")
    except Exception as e:
        ai = None
        logger.error(f"Failed to initialize AIHelper: {e}")

scheduler = SchedulerManager(bot, db, timezone=DEFAULT_TIMEZONE)

# --- Admin persistence (data/admins.json) ---
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")

def load_admins():
    try:
        if os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, "r") as f:
                data = json.load(f) or []
                return set(int(x) for x in data)
    except Exception as e:
        logger.error("Failed to load admins file: %s", e)
    return set()

def save_admins(admins_set):
    try:
        with open(ADMINS_FILE, "w") as f:
            json.dump(sorted(list(admins_set)), f)
    except Exception as e:
        logger.error("Failed to save admins file: %s", e)

ADMINS = load_admins()
# Ensure owner is always an admin
if OWNER_ID:
    ADMINS.add(OWNER_ID)
save_admins(ADMINS)

def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID or (user_id in ADMINS)

# --- Cooldown system ---
user_cooldowns = {}
COOLDOWN_SECONDS = 10  # reduce spam

def can_reply(user_id: str) -> bool:
    now = time.time()
    last_time = user_cooldowns.get(user_id, 0)
    if now - last_time >= COOLDOWN_SECONDS:
        user_cooldowns[user_id] = now
        return True
    return False

# --- Bot identity (lazy) ---
_cached_bot_username = None
_cached_bot_id = None

def refresh_bot_info():
    global _cached_bot_username, _cached_bot_id
    try:
        me = bot.get_me()
        if me:
            _cached_bot_username = (me.username or "").lower()
            _cached_bot_id = getattr(me, "id", None)
    except Exception as e:
        logger.debug("Could not get bot info right now: %s", e)

# initial try
refresh_bot_info()

# --- Should reply logic (with human-reply ignore) ---
def should_reply(msg: types.Message) -> bool:
    # refresh cached bot info if empty
    if not _cached_bot_username or not _cached_bot_id:
        refresh_bot_info()
    bot_username = _cached_bot_username or ""
    bot_id = _cached_bot_id

    # Private chat -> always reply
    try:
        if msg.chat.type == "private":
            return True
    except Exception:
        # fallback if chat type missing
        pass

    # ========== NEW FIX ==========
    # Agar message kisi reply me hai
    if msg.reply_to_message:
        try:
            if msg.reply_to_message.from_user:
                if msg.reply_to_message.from_user.id == bot_id:
                    # Agar reply bot ko diya hai → reply kare
                    return True
                else:
                    # Agar reply kisi aur insaan ko diya hai → ignore
                    return False
        except Exception:
            # On error default to not replying
            return False
    # ==============================

    text = (msg.text or "") + " "  # avoid empty slice errors
    entities = msg.entities or []

    mentioned_someone = False
    mentioned_bot = False

    for ent in entities:
        try:
            # there are 'mention' and 'text_mention' entity types
            if ent.type == "mention":
                mention = text[ent.offset:ent.offset + ent.length].lower()
                mentioned_someone = True
                if bot_username and bot_username in mention:
                    mentioned_bot = True
            elif ent.type == "text_mention":
                mentioned_someone = True
                if ent.user and bot_id and ent.user.id == bot_id:
                    mentioned_bot = True
        except Exception:
            continue

    # If bot is explicitly mentioned -> reply
    if mentioned_bot:
        return True

    # If someone else is mentioned and bot is not -> don't reply
    if mentioned_someone and not mentioned_bot:
        return False

    # Extra: if there's an '@' sign but not bot mention -> skip
    if "@" in text and not mentioned_bot and mentioned_someone:
        return False

    # No mention and no reply -> normal reply
    if not mentioned_someone:
        return True

    return False

# =============== START ==================
@bot.message_handler(commands=["start"])
def start(msg: types.Message):
    db.add_group(msg.chat.id)
    markup = types.InlineKeyboardMarkup()
    try:
        bot_me = bot.get_me()
        if bot_me and bot_me.username:
            add_url = f"https://t.me/{bot_me.username}?startgroup=true"
            markup.add(types.InlineKeyboardButton("➕ Add me to your Group", url=add_url))
    except Exception:
        pass

    markup.add(
        types.InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        types.InlineKeyboardButton("📊 Stats", callback_data="stats"),
        types.InlineKeyboardButton("⚡ Manage Admins", callback_data="manage_admins"),
        types.InlineKeyboardButton("📋 Sticker Grabber", callback_data="sticker_grabber"),
        types.InlineKeyboardButton("📢 Broadcast Manager", callback_data="broadcast_manager")
    )
    markup.add(types.InlineKeyboardButton("💬 Support", url="https://t.me/your_support_channel"))
    bot.reply_to(msg, "🤖 Ultra-Pro AI Bot v3 ready!\nUse /panel for owner controls.", reply_markup=markup)

# =============== OWNER PANEL ==================
@bot.message_handler(commands=["panel"])
def panel(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Not allowed.")
    markup = owner_panel_markup()
    # add broadcast & admin controls to owner panel
    markup.add(types.InlineKeyboardButton("⚡ Manage Admins", callback_data="manage_admins"))
    markup.add(types.InlineKeyboardButton("📋 Sticker Grabber", callback_data="sticker_grabber"))
    markup.add(types.InlineKeyboardButton("📢 Broadcast Manager", callback_data="broadcast_manager"))
    bot.send_message(OWNER_ID, "⚙️ Owner Panel", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: True)
def cb(call: types.CallbackQuery):
    # for most actions allow owner or admins where appropriate
    data = call.data or ""
    try:
        if data.startswith("manage_admins") or data == "sticker_grabber":
            if call.from_user.id != OWNER_ID:
                return bot.answer_callback_query(call.id, "❌ Only owner can do this here.")
        elif data.startswith("broadcast_manager"):
            # let admins open broadcast menu too (in DM)
            if not is_admin(call.from_user.id):
                return bot.answer_callback_query(call.id, "❌ Not allowed.")
    except Exception:
        pass

    try:
        if call.data == "list_groups":
            groups = db.get_groups()
            bot.send_message(OWNER_ID, "📋 Groups:\n" + ("\n".join(map(str, groups)) if groups else "None"))
        elif call.data == "new_schedule":
            bot.send_message(OWNER_ID, "📝 Use /schedule YYYY-MM-DD HH:MM <None/daily/weekly/monthly> Message")
        elif call.data == "instant_broadcast":
            bot.send_message(OWNER_ID, "🚀 Use /broadcast or /broadcast_media")
        elif call.data == "cancel_schedules":
            scheduler.cancel_all(); db.clear_schedules()
            bot.send_message(OWNER_ID, "✅ All schedules cleared.")
        elif call.data == "help":
            bot.send_message(OWNER_ID, "ℹ️ Help: Use /broadcast, /schedule, /panel for controls.")
        elif call.data == "stats":
            g = len(db.get_groups()); u = db.count_users(); s = len(db.list_schedules())
            bot.send_message(OWNER_ID, f"📊 Stats\nGroups:{g}\nUsers:{u}\nSchedules:{s}")
        elif call.data == "manage_admins":
            # owner-only panel: list current admins
            admin_list = "\n".join([f"👤 {uid}" for uid in sorted(ADMINS)])
            bot.send_message(OWNER_ID, f"⚡ Current Admins:\n{admin_list}")
        elif call.data == "sticker_grabber":
            bot.send_message(OWNER_ID, "🖼️ Reply to any sticker with /grabsticker to fetch its file_id.")
        elif call.data == "broadcast_manager":
            # open broadcast menu in DM for the caller
            show_broadcast_menu(call.from_user.id)
        elif call.data.startswith("bc_"):
            # routed to broadcast callback handler defined below
            pass
        # acknowledge callback
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
    except Exception as e:
        logger.error("Callback handler error: %s", e)
        try:
            bot.answer_callback_query(call.id, "⚠️ Error processing action.")
        except Exception:
            pass

# =============== Admin commands (owner) ==================
@bot.message_handler(commands=["addadmin"])
def add_admin(msg: types.Message):
    # Owner only
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only Owner can add admins.")
    try:
        # If reply to a user: use that user's id
        if msg.reply_to_message and msg.reply_to_message.from_user:
            uid = msg.reply_to_message.from_user.id
        else:
            args = msg.text.split()
            if len(args) < 2:
                return bot.reply_to(msg, "Usage: /addadmin <user_id> OR reply to user's message with /addadmin")
            uid = int(args[1])
        ADMINS.add(uid)
        save_admins(ADMINS)
        bot.reply_to(msg, f"✅ User {uid} added as Admin.")
    except Exception as e:
        logger.error("addadmin error: %s", e)
        bot.reply_to(msg, f"⚠️ Failed to add admin: {e}")

@bot.message_handler(commands=["removeadmin"])
def remove_admin(msg: types.Message):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Only Owner can remove admins.")
    try:
        args = msg.text.split()
        if len(args) < 2:
            return bot.reply_to(msg, "Usage: /removeadmin <user_id>")
        uid = int(args[1])
        if uid in ADMINS:
            ADMINS.discard(uid)
            save_admins(ADMINS)
            bot.reply_to(msg, f"✅ User {uid} removed from Admins.")
        else:
            bot.reply_to(msg, f"⚠️ User {uid} is not an Admin.")
    except Exception as e:
        logger.error("removeadmin error: %s", e)
        bot.reply_to(msg, f"⚠️ Failed: {e}")

@bot.message_handler(commands=["listadmins"])
def list_admins(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, "❌ Not allowed.")
    admin_list = "\n".join([str(uid) for uid in sorted(ADMINS)])
    bot.reply_to(msg, f"👑 Current Admins:\n{admin_list}")

# =============== BROADCAST MANAGER (inline + DM wizard) ==================
# sessions: user_id -> dict with state + fields
broadcast_sessions = {}

def show_broadcast_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📝 Text Broadcast", callback_data="bc_text"))
    markup.add(types.InlineKeyboardButton("🖼️ Media + Button", callback_data="bc_media"))
    markup.add(types.InlineKeyboardButton("⏰ Schedule Broadcast", callback_data="bc_schedule"))
    bot.send_message(chat_id, "📢 Broadcast Manager:\nChoose an option ↓", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("bc_"))
def broadcast_cb(call: types.CallbackQuery):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return bot.answer_callback_query(call.id, "❌ Not allowed.")
    data = call.data
    # make sure further conversation happens in private chat (DM)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    if data == "bc_text":
        broadcast_sessions[user_id] = {"state": "await_text"}
        bot.send_message(user_id, "✍️ Send the TEXT you want to broadcast to all groups. Send /cancel to abort.")
    elif data == "bc_media":
        broadcast_sessions[user_id] = {"state": "await_media_upload"}
        bot.send_message(user_id, "📸 Please send the IMAGE or VIDEO you want to broadcast (directly in this chat). Send /cancel to abort.")
    elif data == "bc_schedule":
        # start scheduling wizard
        broadcast_sessions[user_id] = {"state": "await_schedule_type"}
        bot.send_message(user_id, "⏰ Schedule Broadcast Wizard:\nType 'text' or 'media' — which do you want to schedule?")
    else:
        bot.send_message(user_id, "⚠️ Unknown broadcast option.")

@bot.message_handler(commands=["broadcast_menu"])
def cmd_broadcast_menu(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, "❌ Not allowed.")
    show_broadcast_menu(msg.from_user.id)

@bot.message_handler(commands=["cancel"])
def cmd_cancel(msg: types.Message):
    uid = msg.from_user.id
    if uid in broadcast_sessions:
        broadcast_sessions.pop(uid, None)
        bot.reply_to(msg, "❌ Broadcast wizard cancelled.")
    else:
        bot.reply_to(msg, "Nothing to cancel.")

# Handler for private incoming media when in broadcast session
@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user and m.from_user.id in broadcast_sessions, content_types=["photo", "video"])
def _broadcast_receive_media(msg: types.Message):
    uid = msg.from_user.id
    sess = broadcast_sessions.get(uid)
    if not sess:
        return
    state = sess.get("state")
    try:
        if state == "await_media_upload":
            # immediate broadcast media flow
            if msg.photo:
                sess["media_type"] = "photo"
                sess["media_file_id"] = msg.photo[-1].file_id
            elif msg.video:
                sess["media_type"] = "video"
                sess["media_file_id"] = msg.video.file_id
            else:
                return bot.reply_to(msg, "Unsupported media. Send a photo or video.")
            sess["state"] = "await_link"
            bot.send_message(uid, "🔗 Now send the LINK (URL) that the button should open (or /skip to send media without button).")
            return

        if state == "await_schedule_media_upload":
            # schedule media flow
            if msg.photo:
                sess["media_type"] = "photo"
                sess["media_file_id"] = msg.photo[-1].file_id
            elif msg.video:
                sess["media_type"] = "video"
                sess["media_file_id"] = msg.video.file_id
            else:
                return bot.reply_to(msg, "Unsupported media. Send a photo or video.")
            sess["state"] = "await_schedule_link"
            bot.send_message(uid, "🔗 Now send the LINK (URL) for the button (or /skip).")
            return
    except Exception as e:
        logger.error("broadcast media receive error: %s", e)
        bot.reply_to(msg, "⚠️ Error receiving media.")

# Handler for private text steps in broadcast wizard
@bot.message_handler(func=lambda m: m.chat.type == "private" and m.from_user and m.from_user.id in broadcast_sessions, content_types=["text"])
def _broadcast_wizard_text(msg: types.Message):
    uid = msg.from_user.id
    text = (msg.text or "").strip()
    sess = broadcast_sessions.get(uid)
    if not sess:
        return
    state = sess.get("state")

    # Cancel shortcut
    if text.lower() in ("/cancel", "cancel"):
        broadcast_sessions.pop(uid, None)
        return bot.reply_to(msg, "❌ Broadcast wizard cancelled.")

    try:
        # ---------- immediate text broadcast ----------
        if state == "await_text":
            sess["broadcast_text"] = text
            sess["state"] = "await_confirm_text"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Confirm & Send", callback_data=f"bc_confirm_text:{uid}"))
            markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"bc_cancel:{uid}"))
            bot.send_message(uid, "📣 Preview of your broadcast text:\n\n" + text, reply_markup=markup)
            return

        # ---------- immediate media flow: link/button text ----------
        if state == "await_link":
            if text.lower() == "/skip":
                sess["link"] = None
                sess["state"] = "await_caption"
                bot.send_message(uid, "📝 Send the CAPTION for the media (or /skip for no caption).")
                return
            sess["link"] = text
            sess["state"] = "await_btn_text"
            bot.send_message(uid, "🔘 Send the BUTTON TEXT (e.g. Join Channel) or /skip to use default.")
            return

        if state == "await_btn_text":
            if text.lower() == "/skip":
                sess["button_text"] = "Open"
            else:
                sess["button_text"] = text
            sess["state"] = "await_caption"
            bot.send_message(uid, "📝 Send the CAPTION for the media (or /skip for no caption).")
            return

        if state == "await_caption":
            if text.lower() == "/skip":
                sess["caption"] = ""
            else:
                sess["caption"] = text
            # show preview: send media back with button
            sess["state"] = "await_confirm_media"
            markup = types.InlineKeyboardMarkup()
            if sess.get("link"):
                markup.add(types.InlineKeyboardButton(sess.get("button_text", "Open"), url=sess.get("link")))
            # send preview
            if sess.get("media_type") == "photo":
                bot.send_photo(uid, sess["media_file_id"], caption=sess.get("caption", ""), reply_markup=markup if markup.inline_keyboard else None)
            elif sess.get("media_type") == "video":
                bot.send_video(uid, sess["media_file_id"], caption=sess.get("caption", ""), reply_markup=markup if markup.inline_keyboard else None)
            # show confirm/cancel
            confirm_markup = types.InlineKeyboardMarkup()
            confirm_markup.add(types.InlineKeyboardButton("✅ Confirm & Send", callback_data=f"bc_confirm_media:{uid}"))
            confirm_markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data=f"bc_cancel:{uid}"))
            bot.send_message(uid, "Preview above. Confirm to broadcast to all groups where the bot is present.", reply_markup=confirm_markup)
            return

        # ---------- schedule flow ----------
        if state == "await_schedule_type":
            if text.lower() in ("text", "media"):
                sess["schedule_type"] = text.lower()
                sess["state"] = "await_schedule_datetime"
                bot.send_message(uid, "📅 Send SCHEDULE TIME in format: YYYY-MM-DD HH:MM (24h). Example: 2025-09-30 18:30")
            else:
                bot.send_message(uid, "Please reply 'text' or 'media' to select schedule type.")
            return

        if state == "await_schedule_datetime":
            # Basic validation of format
            sess["schedule_datetime"] = text
            sess["state"] = "await_schedule_recur"
            bot.send_message(uid, "🔁 Recurrence? send one of: none / daily / weekly / monthly")
            return

        if state == "await_schedule_recur":
            recur = text.lower()
            if recur not in ("none", "daily", "weekly", "monthly"):
                return bot.send_message(uid, "Choose recurrence: none / daily / weekly / monthly")
            sess["schedule_recur"] = recur
            # next collect message or media depending on type
            if sess.get("schedule_type") == "text":
                sess["state"] = "await_schedule_text"
                bot.send_message(uid, "✍️ Send the TEXT to schedule.")
            else:
                sess["state"] = "await_schedule_media_upload"
                bot.send_message(uid, "📸 Now send the IMAGE or VIDEO to schedule (in this chat).")
            return

        if state == "await_schedule_text":
            # finalize schedule for text
            payload = text
            run_time = sess.get("schedule_datetime")
            recur = sess.get("schedule_recur")
            # call scheduler.schedule_broadcast(run_time, payload, media, recurrence)
            try:
                jobid = scheduler.schedule_broadcast(run_time, payload, None, recur)
                try:
                    db.add_schedule(jobid, payload, None, run_time, recur)
                except Exception:
                    logger.debug("db.add_schedule failed (maybe db not implemented).")
                bot.send_message(uid, f"✅ Scheduled text broadcast at {run_time} recur={recur}. jobid={jobid}")
            except Exception as e:
                logger.exception("Failed to schedule broadcast:")
                bot.send_message(uid, f"⚠️ Failed to schedule: {e}")
            broadcast_sessions.pop(uid, None)
            return

        if state == "await_schedule_link":
            if text.lower() == "/skip":
                sess["schedule_link"] = None
            else:
                sess["schedule_link"] = text
            sess["state"] = "await_schedule_btn_text"
            bot.send_message(uid, "🔘 Send BUTTON TEXT for scheduled media (or /skip).")
            return

        if state == "await_schedule_btn_text":
            if text.lower() == "/skip":
                sess["schedule_btn_text"] = "Open"
            else:
                sess["schedule_btn_text"] = text
            sess["state"] = "await_schedule_caption"
            bot.send_message(uid, "📝 Send CAPTION for scheduled media (or /skip).")
            return

        if state == "await_schedule_caption":
            if text.lower() == "/skip":
                sess["schedule_caption"] = ""
            else:
                sess["schedule_caption"] = text
            # finalize schedule for media
            run_time = sess.get("schedule_datetime")
            recur = sess.get("schedule_recur")
            payload = sess.get("schedule_caption", "")
            media_file_id = sess.get("media_file_id")
            # store schedule in scheduler
            try:
                jobid = scheduler.schedule_broadcast(run_time, payload, media_file_id, recur)
                try:
                    db.add_schedule(jobid, payload, media_file_id, run_time, recur)
                except Exception:
                    logger.debug("db.add_schedule failed (maybe db not implemented).")
                bot.send_message(uid, f"✅ Scheduled media broadcast at {run_time} recur={recur}. jobid={jobid}")
            except Exception as e:
                logger.exception("Failed to schedule media broadcast:")
                bot.send_message(uid, f"⚠️ Failed to schedule: {e}")
            broadcast_sessions.pop(uid, None)
            return

    except Exception as e:
        logger.exception("broadcast wizard text handler error:")
        bot.reply_to(msg, "⚠️ Error during broadcast wizard.")

# Callback handlers for confirm/cancel
@bot.callback_query_handler(func=lambda c: c.data and (c.data.startswith("bc_confirm_") or c.data.startswith("bc_cancel:") ))
def _broadcast_confirm_cancel(call: types.CallbackQuery):
    data = call.data or ""
    try:
        # pattern bc_confirm_text:<uid>, bc_confirm_media:<uid>, bc_cancel:<uid>
        if data.startswith("bc_cancel:"):
            parts = data.split(":", 1)
            uid = int(parts[1]) if len(parts) > 1 else call.from_user.id
            if call.from_user.id != uid:
                return bot.answer_callback_query(call.id, "❌ Not allowed.")
            broadcast_sessions.pop(uid, None)
            bot.answer_callback_query(call.id)
            return bot.send_message(uid, "✅ Broadcast cancelled.")
        if data.startswith("bc_confirm_text:"):
            parts = data.split(":", 1)
            uid = int(parts[1]) if len(parts) > 1 else call.from_user.id
            if call.from_user.id != uid and not is_admin(call.from_user.id):
                return bot.answer_callback_query(call.id, "❌ Not allowed.")
            sess = broadcast_sessions.get(uid)
            if not sess or "broadcast_text" not in sess:
                bot.answer_callback_query(call.id, "⚠️ No text to send.")
                return
            text = sess["broadcast_text"]
            bot.answer_callback_query(call.id, "Sending broadcast...")
            groups = db.get_groups()
            sent = 0
            for gid in groups:
                try:
                    bot.send_message(gid, text)
                    sent += 1
                    time.sleep(0.06)
                except Exception as e:
                    logger.warning("Broadcast text failed to %s: %s", gid, e)
            broadcast_sessions.pop(uid, None)
            bot.send_message(uid, f"✅ Broadcast text sent to {sent} groups.")
            return

        if data.startswith("bc_confirm_media:"):
            parts = data.split(":", 1)
            uid = int(parts[1]) if len(parts) > 1 else call.from_user.id
            if call.from_user.id != uid and not is_admin(call.from_user.id):
                return bot.answer_callback_query(call.id, "❌ Not allowed.")
            sess = broadcast_sessions.get(uid)
            if not sess or "media_file_id" not in sess:
                bot.answer_callback_query(call.id, "⚠️ No media to send.")
                return
            media_type = sess.get("media_type")
            file_id = sess.get("media_file_id")
            caption = sess.get("caption", "")
            link = sess.get("link")
            btn_text = sess.get("button_text", "Open")
            markup = types.InlineKeyboardMarkup()
            if link:
                markup.add(types.InlineKeyboardButton(btn_text, url=link))
            bot.answer_callback_query(call.id, "Sending broadcast...")
            groups = db.get_groups()
            sent = 0
            for gid in groups:
                try:
                    if media_type == "photo":
                        bot.send_photo(gid, file_id, caption=caption or "", reply_markup=markup if markup.inline_keyboard else None)
                    elif media_type == "video":
                        bot.send_video(gid, file_id, caption=caption or "", reply_markup=markup if markup.inline_keyboard else None)
                    sent += 1
                    time.sleep(0.09)
                except Exception as e:
                    logger.warning("Broadcast media failed to %s: %s", gid, e)
            broadcast_sessions.pop(uid, None)
            bot.send_message(uid, f"✅ Broadcast media sent to {sent} groups.")
            return
    except Exception as e:
        logger.exception("broadcast confirm handler error:")
        try:
            bot.answer_callback_query(call.id, "⚠️ Error processing broadcast.")
        except Exception:
            pass

# =============== STICKER GRABBER ==================
@bot.message_handler(commands=["grabsticker"])
def grab_sticker(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return bot.reply_to(msg, "❌ Not allowed.")
    if not msg.reply_to_message or not msg.reply_to_message.sticker:
        return bot.reply_to(msg, "⚠️ Reply to a sticker with this command to grab its file_id.")
    sticker_id = msg.reply_to_message.sticker.file_id
    bot.reply_to(msg, f"✅ Sticker file_id:\n<code>{sticker_id}</code>", parse_mode="HTML")

# =============== CHAT HANDLER ==================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def chat(msg: types.Message):
    if not should_reply(msg):
        return

    if msg.from_user and getattr(msg.from_user, "is_bot", False):
        return

    text = (msg.text or "").strip()
    lower = text.lower()

    # Keywords for triggering image
    image_keywords = ["photo", "pic", "image", "picture", "meme", "photo of", "pic of", "picture of"]

    if any(k in lower for k in image_keywords):
        try:
            bot.send_chat_action(msg.chat.id, "upload_photo")
        except Exception:
            pass

        prompt = text
        img_bytes, err = ai.generate_image(prompt)  # ✅ yaha change kiya

        if img_bytes:
            try:
                bot.send_photo(msg.chat.id, img_bytes, caption="✨ Ye lo — tumhari image! 💖")
            except Exception as e:
                logger.error("send_photo failed: %s", e)
                bot.send_message(msg.chat.id, "⚠️ Image ready, lekin bhejne me problem aayi.")
            return
        else:
            bot.send_message(msg.chat.id, f"⚠️ Image generate nahi ho paayi. {err or ''}")
            # fallthrough to text reply

    # ---------- Normal text reply ----------
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
            reply = ai.chat_reply(
                f"Tum ek ladki ho jiska naam 'Butki' hai 💖\n"
                f"Tumhari personality mast, thodi naughty aur full masti wali hai 😘\n"
                f"Group me behave karo jaise tum sabki dost ho 🥳\n"
                f"Thoda flirty, thoda funny aur emojis ke sath pyara sa reply do 💅✨\n"
                f"User: {msg.text}",
                mem
            )
        except Exception as e:
            logger.error(f"AI error: {e}")
            reply = "⚠️ Sorry baby, abhi thoda busy hoon 💖"

        db.add_memory(uid, "assistant", reply)

        try:
            bot.reply_to(msg, reply)
        except Exception as e:
            logger.error(f"Reply_to failed, fallback: {e}")
            bot.send_message(msg.chat.id, reply)

    except Exception as e:
        logger.exception("Chat error:")
        bot.send_message(msg.chat.id, "⚠️ Error, please try again later.")

# =============== STICKER HANDLER ==================
STICKER_IDS = [
    "CAACAgUAAxkBAAMsaM0_Bknmh1kNnNzEH8GpllJ3HIUAAhsRAAJV8BFUGQQlAfumZL02BA",
    "CAACAgEAAxkBAAMoaM03EtaeDFGFrsRC0MDNSM8LgbIAAu4AAyAK8EYrQPDMf_R-rDYE",
    "CAACAgUAAxkBAAMmaM03DTk-hY3KvaMEPcsK548XFvsAApAUAALFL-BVvNXMv2XTJPg2BA",
    "CAACAgUAAyEFAAStbkSDAAIBzmjNJBx_mcgcx3KBYU1O9dpWegpPAAI7FQACbMwgVFrPF5hMaq5UNgQ",
    "CAACAgUAAxkBAANNaM1VMX0VXi_2ql897hzgwKnlkGQAAjsOAAIKCDlW81YQdhOWt402BA",
]

@bot.message_handler(content_types=["sticker"])
def sticker(msg: types.Message):
    if not should_reply(msg):
        return
    if msg.from_user.is_bot:
        return

    emoji = msg.sticker.emoji if msg.sticker else "🙂"
    try:
        if ai and can_reply(str(msg.from_user.id)) and random.random() < 0.7:
            prompt = (
                f"Tum ek ladki ho jiska naam 'Butki' hai 💖\n"
                f"User ne ek {emoji} sticker bheja hai.\n"
                f"Sticker dekh kar mast funny, flirty aur cute reply do 💅✨\n"
                f"Har reply me emojis use karo jaise ek ladki naturally karti hai 😘"
            )
            try:
                reply = ai.chat_reply(prompt)
            except Exception as e:
                logger.error(f"AI error (sticker): {e}")
                reply = f"{emoji} Awww, kitna cute sticker hai 💖"

            try:
                bot.reply_to(msg, reply)
            except Exception as e:
                logger.error(f"Reply_to failed (sticker), fallback: {e}")
                bot.send_message(msg.chat.id, reply)

        else:
            if STICKER_IDS:
                sticker_id = random.choice(STICKER_IDS)
                bot.send_sticker(msg.chat.id, sticker_id, reply_to_message_id=msg.message_id)
            else:
                bot.send_message(msg.chat.id, f"{emoji} Cute sticker!")

    except Exception as e:
        logger.error(f"Sticker reply error: {e}")
        bot.send_message(msg.chat.id, f"{emoji} (sticker received)")

# =============== GIF ==================
@bot.message_handler(content_types=["animation"])
def gif(msg: types.Message):
    bot.reply_to(msg, "😂🔥 Cool GIF!")

# =============== WELCOME + GOODBYE ==================
WELCOME_MSG = "🌸 Hey {name}, welcome to {chat}! 💖 Butki family me swagat hai 🎉"
GOODBYE_MSG = "👋 Bye {name}, hope to see you again in {chat}! 💫"

@bot.message_handler(content_types=["new_chat_members"])
def welcome(msg: types.Message):
    for user in msg.new_chat_members:
        try:
            text = WELCOME_MSG.format(name=user.first_name, chat=msg.chat.title)
            bot.send_message(msg.chat.id, text)
        except Exception as e:
            logger.error(f"Welcome error: {e}")

@bot.message_handler(content_types=["left_chat_member"])
def goodbye(msg: types.Message):
    user = msg.left_chat_member
    try:
        text = GOODBYE_MSG.format(name=user.first_name, chat=msg.chat.title)
        bot.send_message(msg.chat.id, text)
    except Exception as e:
        logger.error(f"Goodbye error: {e}")

# =============== SCHEDULE COMMAND (owner) ==================
@bot.message_handler(commands=["schedule"])
def schedule(msg):
    if msg.from_user.id != OWNER_ID:
        return
    parts = msg.text.split(" ", 4)
    if len(parts) < 4 and not msg.reply_to_message:
        return bot.reply_to(msg, "Usage: /schedule YYYY-MM-DD HH:MM <recurring> message (or reply to media with caption)")
    try:
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
        try:
            db.add_schedule(jobid, payload, media, run_time, r)
        except Exception:
            logger.debug("db.add_schedule not available or failed.")
        bot.reply_to(msg, f"✅ Scheduled {run_time} recurring={r} jobid={jobid}")
    except Exception as e:
        logger.exception("Schedule command error:")
        bot.reply_to(msg, f"⚠️ Failed to schedule: {e}")

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

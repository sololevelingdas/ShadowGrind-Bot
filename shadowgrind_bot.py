# =================================================================================
# SHADOWGRIND BOT - VERSION 1.5 (CORRECTED & REFACTORED)
# =================================================================================

# --- IMPORTS (CENTRALIZED & CLEANED) ---
import os
import random
import asyncio
import colorsysdef
import textwrap
import io
import traceback
import html
import uuid
import json
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import firebase_admin
from firebase_admin import credentials, firestore
from PIL import Image, ImageDraw, ImageFont
from telegram.request import HTTPXRequest
from datetime import datetime, timezone, timedelta
from functools import wraps


# --- RENDER 24/7 HEARTBEAT ---
app = Flask('')
@app.route('/')
def home():
    return "ShadowGrind System Online"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT CONFIGURATION ---
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
bot_token = os.getenv("BOT_TOKEN")

# Initialize Firebase (Ensure serviceAccountKey.json is in the same folder)
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Error: {e}")

# --- [FIX 2] Added missing PIL/Pillow imports for image generation ---
from PIL import Image, ImageDraw, ImageFont

from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup, # Normal spaces here
    InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)

from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, # Normal spaces here
    CallbackQueryHandler, ContextTypes, filters
)

# --- [FIX 1] Removed extra closing parenthesis that caused a SyntaxError ---
# ) 

from telegram.constants import ParseMode, ChatAction
from telegram.error import Forbidden

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from dotenv import load_dotenv


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # 1. Log the error to your console
    print(f"⚠️ Exception while handling an update: {context.error}")

    # 2. Get the Traceback (the technical error details)
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # 3. Build the User Message (The "Glitch" notification)
    # We check if 'update' is actually a Telegram Update object before trying to reply
    if isinstance(update, Update) and update.effective_message:
        text = (
            "🚫 **SYSTEM ANOMALY DETECTED** 🚫\n\n"
            "An unexpected error occurred within the System logic.\n"
            "The Administrator has been notified.\n\n"
            "_Try your command again in a few moments._"
        )
        try:
            await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            # If we can't send to the user (e.g. they blocked us), just ignore
            pass

    # 4. Build the Admin Report (Sent to YOU)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"🔴 **System Exception Detected**\n\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # 5. Send to Admin
    # We split it if it's too long (Telegram limit is 4096 chars)
    if len(message) > 4000:
        message = message[:4000] + "</pre>\n...(truncated)"
    
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID, 
        text=message, 
        parse_mode=ParseMode.HTML
    )


# ==========================================
# 🎖️ CUSTOM BADGE STYLES
# ==========================================
BADGE_STYLES = {
    "Founder":      "💠 𝐅𝐎𝐔𝐍𝐃𝐄𝐑",    # Special Font + Diamond
    "VIP":          "⚜️ 𝐕.𝐈.𝐏",       # Fleur-de-lis + Bold
    "Honest One":   "⚖️ 𝐇𝐎𝐍𝐄𝐒𝐓",      # Scales of Justice
    "Monarch":      "👑 𝐌𝐎𝐍𝐀𝐑𝐂𝐇",     # Crown + Serif Font
    "S-Rank":       "⚡ 𝐒-𝐑𝐀𝐍𝐊",      # Lightning + Bold
    "Bug Hunter":   "🐛 𝐇𝐔𝐍𝐓𝐄𝐑"       # Fallback
}

def get_badge_display(user_data, mode="inline"):
    """
    Returns badges formatted for Profile (list) or Leaderboard (inline).
    """
    badges = user_data.get("badges", [])
    if not badges: return ""

    display_str = ""
    
    if mode == "inline":
        # For Leaderboard: Short icons only to save space
        # Example: 👑⚜️ Sarath
        icon_map = {
            "Founder": "💠", 
            "VIP": "⚜️", 
            "Honest One": "⚖️", 
            "Monarch": "👑", 
            "S-Rank": "⚡"
        }
        for b in badges:
            display_str += icon_map.get(b, "")
        return display_str + " " # Spacer
        
    elif mode == "profile":
        # For Profile: Full fancy tags
        # Example: 
        # 💠 𝐅𝐎𝐔𝐍𝐃𝐄𝐑
        # ⚜️ 𝐕.𝐈.𝐏
        tags = []
        for b in badges:
            style = BADGE_STYLES.get(b, f"🏷️ {b.upper()}")
            tags.append(f"│  {style}") # Adds a cool vertical line tree effect
        return "\n".join(tags) + "\n"

    return ""



# --- DECORATORS ---
def admin_only(func):
    """Decorator to restrict a command to the admin user."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if str(update.effective_user.id) != ADMIN_USER_ID:
            await update.message.reply_text("🚫 This action can only be performed by the System Administrator.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# --- (Add this to your DECORATORS section) ---

def check_active_status(func):
    """
    Decorator that checks if a user is registered, activated,
    not banned, and has an active subscription.
    This replaces the manual checks at the start of most commands.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id)
        if user_id == ADMIN_USER_ID:
            # Admin bypasses all checks
            return await func(update, context, *args, **kwargs)
            
        user_doc = db.collection("users").document(user_id).get()
        message = update.message or update.callback_query.message # Get the message object
        
        if not user_doc.exists or "level" not in user_doc.to_dict():
            await message.reply_text("⚠️ You must complete onboarding and activate your contract first. Use /start.")
            return

        user_data = user_doc.to_dict()

        # 1. Check if Banned
        if user_data.get("is_banned", False):
            await message.reply_text(
                "**ACCOUNT LOCKED**\n\n"
                "Your connection to the System has been severed by an Administrator.\n"
                "Contact support for more information."
            )
            return
            
        # 2. Check if Expired
        expires_at = user_data.get("expires_at", datetime.now(timezone.utc))
        if datetime.now(timezone.utc) > expires_at:
            await message.reply_text(
                "⛓️ **Contract Expired** ⛓️\n\n"
                "Your access to the ShadowGrind Protocol has expired.\n"
                "Please enter a new activation code to renew your contract."
            )
            # Set state to awaiting_code for easy renewal
            db.collection("users").document(user_id).update({"state": "awaiting_code"})
            return

        # If all checks pass, run the original command
        return await func(update, context, *args, **kwargs)
    return wrapper



def leader_only(func):
    """Decorator to restrict a command to the user's guild leader."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id)
        user_doc = db.collection("users").document(user_id).get()

        if not user_doc.exists:
            await update.message.reply_text("❌ You don't seem to be registered.")
            return

        user_data = user_doc.to_dict()
        if user_data.get("guild_role") != "Leader":
            await update.message.reply_text("🚫 This action can only be performed by the Guild Leader.")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper



def leadership_only(func):
    """Decorator to restrict a command to Guild Leaders AND Officers."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id)
        user_doc = db.collection("users").document(user_id).get()

        if not user_doc.exists:
            await update.message.reply_text("❌ You don't seem to be registered.")
            return

        user_data = user_doc.to_dict()
        role = user_data.get("guild_role")
        
        if role not in ["Leader", "Officer"]:
            await update.message.reply_text("🚫 This action requires Officer privileges or higher.")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper




#honorrrr

# --- Constants for Honor Code (Fixed HTML Version) ---
HONOR_CODE_TEXT = (
    "<b>📜 THE ABYSSAL OATH // HUNTER'S HONOR 📜</b>\n\n"
    "Before drawing power from the System, swear the Oath. This binds Hunter and Shadow:\n\n"
    "1. <b>VOW OF STEEL</b> ⚔️\n"
    "<i>Commitment Forged in Shadow.</i> Missions accepted demand unwavering resolve. Undertake them with purpose; see them through.\n\n"
    "2. <b>ECHO OF TRUTH</b> 👁️\n"
    "<i>Honesty is the Blade's Edge.</i> The System perceives all. Submit proof reflecting genuine struggle and true accomplishment. Deception invites weakness.\n\n"
    "3. <b>ASCENSION THROUGH STRIFE</b> 🔥\n"
    "<i>Failure is but a Sharpening Stone.</i> Stumble, rise, learn. Persistence carves the path to power. Embrace adversity.\n\n"
    "Do you swear upon your shadow to uphold this Abyssal Oath?"
)

HONOR_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ I Swear the Oath", callback_data="honor_accept"),
        InlineKeyboardButton("❌ I Refuse the Path", callback_data="honor_decline"),
    ]
])


# --- CONFIGURATION ---
load_dotenv()
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "1419440031") # Your Admin Telegram User ID
bot_token = os.getenv("BOT_TOKEN")


FONT_FILE_REGULAR = "Exo2-Regular.ttf"
FONT_FILE_BOLD = "Exo2-Bold.ttf"
MIN_RANK_TO_CREATE_GUILD = "D"
MAX_GUILD_MEMBERS = 20

# --- PROGRESSION CONSTANTS ---
XP_REQ_E = 1000   # Lv 1-9 (1000 per level)
XP_REQ_D = 2000   # Lv 10-24 (2000 per level)
XP_REQ_C = 4000   # Lv 25-44 (4000 per level)
XP_REQ_B = 8000   # Lv 45-69 (8000 per level)
XP_REQ_A = 16000  # Lv 70-99 (16000 per level)
XP_REQ_S = 32000  # Lv 100+  (32000 per level)

# Define which levels trigger a Rank Up
RANK_UP_LEVELS = { "E": 10, "D": 25, "C": 45, "B": 70, "A": 100 }
RANK_UP_QUESTS = {
    "E": [
        {"task": "Perform a single, continuous workout session lasting at least 45 minutes.", "proof_type": "log"},
        {"task": "Engage in one hour of deep, focused work or study with zero digital distractions.", "proof_type": "log"},
        {"task": "Perform 20 minutes of uninterrupted meditation or reflection, focusing on your long-term goals.", "proof_type": "log"}
    ],
    "D": [
        {"task": "Forge consistency. For seven (7) consecutive days, you must complete a minimum of 30 minutes of physical activity each day. Missing a single day resets the trial.", "proof_type": "log"},
        {"task": "Forge focus. For seven (7) consecutive days, dedicate 45 minutes to deep work or focused skill acquisition. No distractions allowed.", "proof_type": "log"},
        {"task": "Forge discipline. For seven (7) consecutive days, practice 15 minutes of mindfulness or journaling upon waking up, BEFORE checking any digital devices.", "proof_type": "log"}
    ],
    "C": [
        {"task": "Prove your endurance. Within a single 48-hour period, you must complete the following: a 10km run, AND a high-volume strength circuit of 100 pull-ups, 200 push-ups, and 300 squats (these can be broken into sets).", "proof_type": "log"},
        {"task": "Prove your mental fortitude. Successfully complete a 24-hour 'Dopamine Detox'. This means no internet (except for essential work/school), no social media, no music, no streaming services, no video games, and no junk food for a full 24 hours.", "proof_type": "log"},
        {"task": "Prove your social courage. Complete the 'Vow of Silence' mission for 8 continuous waking hours in a single day.", "proof_type": "log"}
    ],
    "B": [
        {"task": "Demonstrate leadership. Identify one person in your life and become their accountability partner for two full weeks. You must help them set a small goal and check in with them at least 3 times per week to offer genuine support and encouragement.", "proof_type": "log"},
        {"task": "Provide value. Create and publish a piece of high-value content online. This can be a detailed blog post teaching a skill, a well-edited YouTube video explaining a concept, a useful code repository, or a significant piece of digital art.", "proof_type": "log"},
        {"task": "Show commitment. Over a period of 4 weeks (28 days), you must accumulate a total of 20 hours of physical activity AND 20 hours of focused deep work.", "proof_type": "log"}
    ],
    "A": [
        {"task": "The Vow: Define and commit to a single, transformational keystone habit that you will perform EVERY SINGLE DAY for 30 days without fail. The habit must be significant (e.g., 'Wake up at 5 AM and exercise for 1 hour,' 'Write 1000 words,' 'Code for 2 hours on a major project'). Submit your vow as the log for this task.", "proof_type": "log"},
        {"task": "The Execution: Perform your vowed habit for 30 consecutive days. You must submit a proof log for this trial EVERY SINGLE DAY. Missing a single day resets the entire trial to Day 1.", "proof_type": "log"},
        {"task": "The Synthesis: On the 31st day, submit a final 'After-Action Report' (at least 500 words) detailing your 30-day journey. It must analyze your struggles, your breakthroughs, and how the process has fundamentally changed your identity and discipline.", "proof_type": "log"}
    ]
}

DIFFICULTIES = ["Easy", "Intermediate", "Advanced", "Extreme"]
TYPES = ["Physical", "Mental", "Spiritual", "All-Round"]


# --- CONSUMABLE ITEM CONFIGURATION ---
# Key: The exact Item ID from your database (lowercase with underscores)
CONSUMABLE_EFFECTS = {
    # --- XP BOOSTERS (The "Scrolls" & "Knowledge" items) ---
    "scroll_of_insight": {
        "name": "Scroll of Insight",
        "type": "xp_boost", 
        "value": 1.5,   # +50% XP
        "duration_minutes": 60,
        "desc": "Deepens understanding. Grants 1.5x XP for 1 hour."
    },
    "scroll_of_deep_focus": {
        "name": "Scroll of Deep Focus",
        "type": "xp_boost",
        "value": 2.0,   # Double XP (High Value!)
        "duration_minutes": 30,
        "desc": "Absolute concentration. Grants 2.0x XP for 30 mins."
    },
    "vial_of_wisdom": {
        "name": "Vial of Wisdom",
        "type": "xp_boost",
        "value": 1.3, 
        "duration_minutes": 120,
        "desc": "Liquid knowledge. Grants 1.3x XP for 2 hours."
    },
    "titan's_blood": {
        "name": "Titan's Blood",
        "type": "xp_boost",
        "value": 2.5,   # Massive Boost (Premium Item)
        "duration_minutes": 15,
        "desc": "Surge of primal power. Grants 2.5x XP for 15 mins."
    },

    # --- LOOT BOOSTERS (Luck & Efficiency items) ---
    "lubricant_of_the_joints": {
        "name": "Lubricant of the Joints",
        "type": "loot_boost",
        "value": 0.15,  # +15% Drop Chance
        "duration_minutes": 60,
        "desc": "Increases agility. +15% Loot Drop Chance for 1 hour."
    },
    "observer's_eye": {
        "name": "Observer's Eye",
        "type": "loot_boost", 
        "value": 0.25,  # +25% Drop Chance
        "duration_minutes": 45,
        "desc": "See the hidden. +25% Loot Drop Chance for 45 mins."
    },
    "metabolic_crystal": {
        "name": "Metabolic Crystal",
        "type": "loot_boost",
        "value": 0.10, 
        "duration_minutes": 120,
        "desc": "Sustained energy. +10% Loot Drop Chance for 2 hours."
    },
    # ... inside CONSUMABLE_EFFECTS = { ...

    # --- SPECIAL LONG-TERM BUFFS ---
    "monarchs_decree": {
        "name": "Monarch's Decree",
        "type": "xp_boost",
        "value": 2.0,           # 2x Multiplier (Double XP)
        "duration_minutes": 10080, # 7 Days (7 * 24 * 60)
        "desc": "Absolute Authority. Grants 2x XP for 7 Days."
    },
    
    # --- SPECIAL (Phoenix Down) ---
    "phoenix_down": {
        "name": "Phoenix Down",
        "type": "xp_boost", # Re-using XP boost for now, can be "Death Protection" later
        "value": 1.1,
        "duration_minutes": 1440, # 24 Hours
        "desc": "The fire of rebirth. +10% XP for 24 hours."
    }
}




# --- DAILY REWARD CONFIGURATION ---
DAILY_BASE_XP = 100
DAILY_STREAK_BONUS_XP = 20 # Extra XP per day of streak
DAILY_MILESTONE_ITEM = "scroll_of_insight" # Item given every 7 days


# --- EQUIPMENT CONFIGURATION ---
# Format: "item_id": {"slot": "Head/Body/Hand/Ring", "bonus_type": "xp/loot", "value": 0.0}
EQUIPMENT_STATS = {
    # --- RINGS ---
    "void_ring": {"slot": "Ring", "bonus_type": "xp", "value": 0.10, "name": "Void Ring"}, # +10% XP
    "shadowflame_ring": {"slot": "Ring", "bonus_type": "loot", "value": 0.15, "name": "Shadowflame Ring"},
    
    # --- ARMOR (Body) ---
    "soulbound_armor": {"slot": "Body", "bonus_type": "xp", "value": 0.20, "name": "Soulbound Armor"},
    "soul_weaver's_robe": {"slot": "Body", "bonus_type": "loot", "value": 0.10, "name": "Soul Weaver's Robe"},
    
    # --- HEADGEAR ---
    "whisperwind_hood": {"slot": "Head", "bonus_type": "loot", "value": 0.05, "name": "Whisperwind Hood"},
    
    # --- WEAPONS (Main Hand) ---
    "phantom_blade": {"slot": "Hand", "bonus_type": "xp", "value": 0.15, "name": "Phantom Blade"}
}

# Define valid slots for display order
VALID_SLOTS = ["Hand", "Head", "Body", "Ring"]



# --- BOT & DATABASE SETUP ---
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"FATAL ERROR: Could not initialize Firebase. Check your 'serviceAccountKey.json'. Error: {e}")
    exit()


# --- (Add this in your CONFIGURATION section) ---

# --- Reply Keyboard Buttons (Chat Input Area) ---
MAIN_REPLY_KEYBOARD_LAYOUT = [
    # Row 1
    [KeyboardButton("\U0001f4dc Mission"), KeyboardButton("\U0001f464 Profile")], # Scroll 📜, Bust in Silhouette 👤
    # Row 2
    [KeyboardButton("\U0001f9f3 Inventory"), KeyboardButton("\U0001f3ad Black Market")], # Backpack 🎒, Mask 🎭
    # Row 3
    [KeyboardButton("\U0001f6e1\ufe0f Guild Hall"), KeyboardButton("\U0001f47b Regiment")], # Shield 🛡️, Ghost 👻
    # Row 4
    [KeyboardButton("\U0001f513 Activate"), KeyboardButton("\u2753 Explain Cmds")] # Lock 🔓, Question Mark ❓
]
MAIN_REPLY_MARKUP = ReplyKeyboardMarkup(MAIN_REPLY_KEYBOARD_LAYOUT, resize_keyboard=True)


async def send_mission_lore(update, context, mission_data):
    """Separate helper to send the lore text bubble."""
    message = update.message or update.callback_query.message
    lore_text = (
        f"\U0001f4e9 **SYSTEM MEMO // MISSION LORE**\n"
        f"----------------------------\n"
        f"_{mission_data.get('description', 'The System provides no context.')}_\n"
        f"----------------------------"
    )
    await context.bot.send_message(chat_id=message.chat_id, text=lore_text, parse_mode=ParseMode.MARKDOWN)




# --- (Add these in your CONFIGURATION section) ---

# --- Premium Inline Menu System ---
SYSTEM_MENU_TEXT = "\u2699\ufe0f **SYSTEM INTERFACE** \u2699\ufe0f\n\nAccess available sub-routines:"

COMMAND_EXPLANATIONS = {
    # --- Core & Retention ---
    "mission": "📜 **Mission Protocol:** Request a new contract. Earn XP, Loot, and Guild XP.",
    "daily": "🗓️ **Daily Login:** Claim your daily supply drop. Build streaks for better rewards.",
    "profile": "👤 **Hunter Profile:** View your Rank, Level, XP, and stats.",
    "status": "⏳ **Contract Status:** Check your subscription expiry date.",
    "leaderboard": "🏆 **Hunter Rankings:** View the top players on the server.",
    
    # --- Inventory & Economy ---
    "inventory": "🎒 **Inventory:** View all your items (Consumables, Gear, Materials).",
    "use": "⚡ **Consume Item:** Use a potion or scroll for a temporary buff.\nUsage: `/use Item Name`",
    "blackmarket": "🎭 **Black Market:** Buy items listed by other players.",
    "sell": "💰 **Sell Item:** List an item for sale.\nUsage: `/sell \"Item Name\" Price`",
    "buy": "🛒 **Buy Item:** Purchase a listed item.\nUsage: `/buy \"Item Name\"`",
    "what": "❓ **Asset List:** View valid sellable items and instructions.",

    # --- The Armory (Equipment) ---
    "loadout": "🥋 **Loadout:** View your currently equipped gear and total passive bonuses.",
    "equip": "⚔️ **Equip Gear:** Wear an item to gain permanent stats.\nUsage: `/equip Item Name`",
    "unequip": "📦 **Remove Gear:** Take off an item.\nUsage: `/unequip Slot`",

    # --- The Forge (Crafting) ---
    "recipes": "⚒️ **Blueprints:** View available crafting recipes.",
    "craft": "🔥 **Forge Item:** Create gear or consumables from materials.\nUsage: `/craft Item Name`",

    # --- Guild System ---
    "guild_hall": "🛡️ **Guild Hall:** The main hub for your Guild.",
    "guild_mission": "📜 **Guild Contract:** View the active cooperative mission.",
    "guild_treasury": "🏦 **Vault:** View items stored in the guild bank.",
    "guild_donate": "🤝 **Donate:** Give items to the guild.\nUsage: `/guild_donate`",
    "leaderboard_guilds": "🏆 **Guild Rankings:** See the top Guilds by Level and XP.",
    
    # --- Guild Management ---
    "guild_create": "⚜️ **Found Guild:** Create a new guild (Requires Rank D+).",
    "guild_invite": "📨 **Recruit:** (Leader/Officer) Invite a user to your guild.",
    "guild_kick": "👢 **Expel:** (Leader/Officer) Remove a member.",
    "guild_promote_officer": "🎖️ **Promote:** (Leader) Make a member an Officer.",
    "guild_leave": "🚪 **Leave:** Exit your current guild.",

    # --- Other ---
    "regiment": "👻 **Shadows:** View your army of extracted soldiers.",
    "worldboss": "🐲 **World Boss:** Check the status of the current raid boss.",
    "activate": "🔓 **Activate:** Enter a code to renew your access."
}

# --- (Add these lines in your CONFIGURATION section) ---

# File IDs for static media assets to prevent re-uploading
COMMON_DROP_FILE_ID = "AgACAgUAAxkBAAIG-GjrUBc1oRwxvOQGC4QOS4A4864xAALQC2sbPB1YVxVCNUT3wyWBAQADAgADeQADNgQ"
SPECIAL_DROP_FILE_ID = "AgACAgUAAxkBAAIG-2jrUEiWIxkbW8LekUlATxvsnk92AALRC2sbPB1YV_MQlu9ZzRG_AQADAgADeQADNgQ"
SUCCESS_VOICE_FILE_ID = "AwACAgUAAxkBAAIHA2jrVabmtCiOLvloPY6dWKNy6D8vAAInGwACPB1YVw_Bi-S1UxGZNgQ"
# --- (Add these lines in your CONFIGURATION section, below the loot drop IDs) ---

# File IDs for static background images
BG_WELCOME_FILE_ID = "AgACAgUAAxkBAAIIt2j13NWL9yWCNOOroUnf3ramU20UAAIYDGsbqYixV59jpMKyzgQsAQADAgADeQADNgQ"
BG_SELL_FILE_ID = "AgACAgUAAxkBAAIItGj13KkbNsJVZZtzFR1-sqV8jNm4AAIXDGsbqYixV9yAucLTsWxiAQADAgADeQADNgQ"
BG_BUY_FILE_ID = "AgACAgUAAxkBAAIIsWj13GPu00-YaJ8gP8dQx2_e4Ie8AAIVDGsbqYixVyf8Wl3QwhebAQADAgADeQADNgQ"
BG_BLACKMARKET_FILE_ID = "AgACAgUAAxkBAAIIrmj13ER959YLiPB1wC7-mSh4OjokAAIQDGsbqYixV9f0yLGmYeRRAQADAgADeQADNgQ"
BG_WHAT_FILE_ID = "AgACAgUAAxkBAAIIumj13PnJAedrR7VR6K0iqGPKHv-oAAIaDGsbqYixVzIHCB7je2hRAQADAgADeQADNgQ"
# PROFILE_BG_FILE_ID = "AgACAgUAAxkBAAIIvWj13azLIcjlAAGXV2D3YHUXeQABSlYAAhsMaxupiLFXHFArBT9HLR4BAAMCAAN5AAM2BA" 
# --- (Add this to your CONFIGURATION section, near the other BG_ FILE_IDs) ---
BG_GUILD_HALL_FILE_ID = "AgACAgUAAxkBAAIJpmj3EqjAZnYLJMcezwqOcr_6UrxTAALcC2sbqYi5V6D7JwUIs50mAQADAgADeQADNgQ" # <-- REPLACE THIS



# --- (Add these in your CONFIGURATION section) ---

# Guild Progression Constants
GXP_CONTRIBUTION_RATE = 0.15  # 15% of user's mission XP goes to the guild
GUILD_XP_PER_LEVEL_BASE = 5000  # XP required for Guild Level 1 to 2
GUILD_LEVEL_MULTIPLIER = 1.2  # Each level requires 1.2x the XP of the last

# Defines perks unlocked at specific guild levels
GUILD_PERK_MILESTONES = {
    3: {"name": "Shadow's Echo", "description": "+2% XP for all members", "effect": "xp_boost_0.02"},
    5: {"name": "Abyssal Bounty", "description": "+1% Loot Drop Chance for all members", "effect": "loot_boost_0.01"},
    7: {"name": "Guild Unity", "description": "+5% GXP Contribution", "effect": "gxp_boost_0.05"},
    10: {"name": "Monarch's Favor", "description": "+5% XP for all members", "effect": "xp_boost_0.05"}
    # Add more levels and perks here
}


# --- HELPER FUNCTIONS ---
def get_rank_sort_value(rank):
    """Converts a rank string to a sortable numerical value (lower is better)."""
    ranks = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
    return ranks.get(str(rank).upper(), 10)





async def trigger_audit(update, context, user_data, mission_data, minutes, reason_tag):
    """Sends the user's proof to the Admin for manual review."""
    user_id = str(update.effective_user.id)
    username = user_data.get("player_name", "Unknown")
    mission_title = mission_data.get("title", "Unknown Mission")
    mission_log = " ".join(context.args)

    # 1. Notify User (The "Fear" Message)
    await update.message.reply_text(
        "⚠️ **SYSTEM ALERT: MANUAL AUDIT TRIGGERED** ⚠️\n\n"
        "Your performance metrics have flagged this submission for review.\n"
        "The Monarch will personally verify your proof.\n\n"
        "__XP withheld pending approval.__",
        parse_mode=ParseMode.MARKDOWN
    )

    # 2. Send to Admin (You)
    audit_keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"audit_pass_{user_id}"),
            InlineKeyboardButton("⚡ PUNISH (-50 XP)", callback_data=f"audit_fail_{user_id}")
        ]
    ]
    
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"🕵️ **AUDIT TRAP TRIGGERED**\n\n"
             f"**Reason:** `{reason_tag}`\n"
             f"**Hunter:** @{username}\n"
             f"**Mission:** {mission_title}\n"
             f"**Time:** {int(minutes)} minutes\n"
             f"**Proof:** _{mission_log}_\n\n"
             f"Decide their fate.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(audit_keyboard)
    )

# --- (Add these to your HELPER FUNCTIONS section) ---

def generate_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(" core Actions", callback_data="menu_category_core")],
        [InlineKeyboardButton(" Economy Hub", callback_data="menu_category_economy")],
        [InlineKeyboardButton(" Guild Operations", callback_data="menu_category_guild")],
        [InlineKeyboardButton(" Shadow Regiment", callback_data="menu_category_regiment")],
        # [InlineKeyboardButton(" World Boss", callback_data="menu_category_worldboss")], # Optional
        [InlineKeyboardButton(" System/Help", callback_data="menu_category_system")]
    ]
    return InlineKeyboardMarkup(keyboard)

def generate_core_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(" Mission", callback_data="run_command_mission"),
            InlineKeyboardButton("?", callback_data="explain_command_mission")
        ],
        [
            InlineKeyboardButton(" Profile", callback_data="run_command_profile"),
            InlineKeyboardButton("?", callback_data="explain_command_profile")
        ],
        [
            InlineKeyboardButton(" Inventory", callback_data="run_command_inventory"),
            InlineKeyboardButton("?", callback_data="explain_command_inventory")
        ],
        [
            InlineKeyboardButton(" Leaderboard", callback_data="run_command_leaderboard"),
             InlineKeyboardButton("?", callback_data="explain_command_leaderboard")
        ],
        [InlineKeyboardButton("< Back", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def generate_economy_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(" Browse Market", callback_data="run_command_blackmarket"),
            InlineKeyboardButton("?", callback_data="explain_command_blackmarket")
        ],
        [
            InlineKeyboardButton(" Sell Item", callback_data="run_command_sell"),
            InlineKeyboardButton("?", callback_data="explain_command_sell")
        ],
        [
            InlineKeyboardButton(" Buy Item", callback_data="run_command_buy"), # Note: Buy still needs user text input after button
            InlineKeyboardButton("?", callback_data="explain_command_buy")
        ],
        [
            InlineKeyboardButton(" My Sellable Items", callback_data="run_command_what"),
            InlineKeyboardButton("?", callback_data="explain_command_what")
        ],
        [InlineKeyboardButton("< Back", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def generate_guild_menu_keyboard():
    keyboard = [
        [ # Core Guild Actions
            InlineKeyboardButton(" Guild Hall", callback_data="run_command_guild_hall"),
            InlineKeyboardButton("?", callback_data="explain_command_guild_hall")
        ],
         [ # Separator can be added if needed
            InlineKeyboardButton(" View Contract", callback_data="run_command_guild_mission"),
            InlineKeyboardButton("?", callback_data="explain_command_guild_mission")
         ],
        [
            InlineKeyboardButton(" View Vault", callback_data="run_command_guild_treasury"),
            InlineKeyboardButton("?", callback_data="explain_command_guild_treasury")
        ],
        [
            InlineKeyboardButton(" Donate Item", callback_data="run_command_guild_donate"),
            InlineKeyboardButton("?", callback_data="explain_command_guild_donate")
        ],
        [
            InlineKeyboardButton(" Roster", callback_data="run_command_guild_members"),
            InlineKeyboardButton("?", callback_data="explain_command_guild_members")
        ],
        # Add buttons for invite, kick, leave, create based on role? Or keep simple?
        [InlineKeyboardButton("< Back", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def generate_regiment_menu_keyboard():
     keyboard = [
        [
            InlineKeyboardButton(" View Regiment", callback_data="run_command_regiment"),
            InlineKeyboardButton("?", callback_data="explain_command_regiment")
        ],
        [InlineKeyboardButton("< Back", callback_data="menu_main")]
    ]
     return InlineKeyboardMarkup(keyboard)

# Optional World Boss Menu
# def generate_worldboss_menu_keyboard(): ...

def generate_system_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(" Contract Status", callback_data="run_command_status"),
            InlineKeyboardButton("?", callback_data="explain_command_status")
        ],
        [
            InlineKeyboardButton(" Activate Code", callback_data="run_command_activate"),
            InlineKeyboardButton("?", callback_data="explain_command_activate")
        ],
        [
            InlineKeyboardButton(" Show Text Commands", callback_data="run_command_help"),
            InlineKeyboardButton("?", callback_data="explain_command_help")
        ],
        [InlineKeyboardButton("< Back", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def generate_explanation_keyboard(back_target: str):
    # back_target should be like 'menu_main' or 'menu_category_core'
    keyboard = [ [InlineKeyboardButton("< Back", callback_data=back_target)] ]
    return InlineKeyboardMarkup(keyboard)

# --- HELPER FUNCTIONS ---
def get_rank_sort_value(rank):
    """Converts a rank string to a sortable numerical value (lower is better)."""
    ranks = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
    return ranks.get(str(rank).upper(), 10)

# --- PASTE THE 3 FUNCTIONS HERE ---

def get_xp_req_for_level(level):
    """Returns how much XP is needed to complete the CURRENT level."""
    if level < 10: return XP_REQ_E
    if level < 25: return XP_REQ_D
    if level < 45: return XP_REQ_C
    if level < 70: return XP_REQ_B
    if level < 100: return XP_REQ_A
    return XP_REQ_S

def get_level_start_xp(level):
    """Calculates the cumulative XP required to REACH the start of this level."""
    if level <= 1: return 0
    
    # E-Rank (Lv 1-9)
    if level <= 10: 
        return (level - 1) * XP_REQ_E
    
    # D-Rank (Lv 10-24)
    # Base for Lv 10 (9000) + (levels into D-rank * 2000)
    if level <= 25: 
        return 9000 + (level - 10) * XP_REQ_D
        
    # C-Rank (Lv 25-44)
    # Base for Lv 25 (39000) + ...
    if level <= 45: 
        return 39000 + (level - 25) * XP_REQ_C
        
    # B-Rank (Lv 45-69)
    if level <= 70: 
        return 119000 + (level - 45) * XP_REQ_B
        
    # A-Rank (Lv 70-99)
    if level <= 100: 
        return 319000 + (level - 70) * XP_REQ_A
        
    # S-Rank (Lv 100+)
    return 799000 + (level - 100) * XP_REQ_S

def calculate_level_from_xp(total_xp):
    """Reverse calculates the level based on Total XP."""
    if total_xp < 9000:   return (total_xp // XP_REQ_E) + 1
    if total_xp < 39000:  return 10 + ((total_xp - 9000) // XP_REQ_D)
    if total_xp < 119000: return 25 + ((total_xp - 39000) // XP_REQ_C)
    if total_xp < 319000: return 45 + ((total_xp - 119000) // XP_REQ_B)
    if total_xp < 799000: return 70 + ((total_xp - 319000) // XP_REQ_A)
    return 100 + ((total_xp - 799000) // XP_REQ_S)
# ----------------------------------

# ... other helper functions follow ...




#armorrrrrssssss
@check_active_status
async def equip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Equips an item from inventory to the correct loadout slot."""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/equip <Item Name>`\nExample: `/equip Void Ring`", parse_mode=ParseMode.MARKDOWN)
        return

    # 1. Normalize Input
    raw_input = " ".join(context.args).strip()
    clean_input = raw_input.lower().replace(" ", "_").replace("'", "").replace("’", "")
    
    # 2. Find Item in Config
    item_id = None
    stats = None
    
    # Check direct ID match first
    if clean_input in EQUIPMENT_STATS:
        item_id = clean_input
        stats = EQUIPMENT_STATS[clean_input]
    else:
        # Fuzzy search keys
        for key, data in EQUIPMENT_STATS.items():
            clean_key = key.lower().replace("'", "").replace("’", "")
            if clean_key == clean_input:
                item_id = key
                stats = data
                break
    
    if not stats:
        await update.message.reply_text(f"❌ **{raw_input}** cannot be equipped (or check spelling).")
        return

    official_name = stats["name"]
    target_slot = stats["slot"]

    # 3. DB Transaction to Swap Gear
    user_ref = db.collection("users").document(user_id)
    
    try:
        @firestore.transactional
        def equip_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            user_data = snapshot.to_dict()
            inventory = user_data.get("inventory", {})
            loadout = user_data.get("loadout", {}) # New field: {"Head": "item_id", "Body": "item_id"}
            
            # Check if user actually has the item
            # We check specific ID or Official Name
            inv_key = None
            if inventory.get(item_id, 0) > 0: inv_key = item_id
            elif inventory.get(official_name, 0) > 0: inv_key = official_name
            
            if not inv_key:
                raise ValueError(f"You do not possess **{official_name}**.")

            # Prepare updates
            updates = {}
            
            # A. Remove new item from inventory
            updates[f"inventory.{inv_key}"] = firestore.Increment(-1)
            
            # B. Check if slot is occupied (Unequip old item)
            old_item_id = loadout.get(target_slot)
            if old_item_id:
                # Find the official name for the old item to put back in inventory
                # (Simple fallback: assume ID is the key, but ideally check stats)
                old_stats = EQUIPMENT_STATS.get(old_item_id)
                old_name = old_stats["name"] if old_stats else old_item_id
                updates[f"inventory.{old_name}"] = firestore.Increment(1)
            
            # C. Set new item in loadout
            updates[f"loadout.{target_slot}"] = item_id
            
            transaction.update(ref, updates)
            return old_item_id

        transaction = db.transaction()
        swapped_item = equip_transaction(transaction, user_ref)
        
        msg = f"🛡️ **EQUIPPED:** {official_name} `[{target_slot}]`"
        if swapped_item:
            old_name = EQUIPMENT_STATS.get(swapped_item, {}).get("name", swapped_item)
            msg += f"\n(Swapped with {old_name})"
            
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    except ValueError as e:
        await update.message.reply_text(f"❌ {e}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"Equip error: {e}")
        await update.message.reply_text("❌ System error while equipping.")




@check_active_status
async def loadout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays current equipment and total passive bonuses."""
    user_id = str(update.effective_user.id)
    user_doc = db.collection("users").document(user_id).get()
    loadout_data = user_doc.to_dict().get("loadout", {})
    
    if not loadout_data:
        await update.message.reply_text("🥋 **Your Loadout is Empty.**\nUse `/equip <item>` to wear gear.")
        return

    # Calculate Totals
    total_xp_boost = 0.0
    total_loot_boost = 0.0
    text_lines = []

    # Iterate through standard slots for order
    for slot in VALID_SLOTS:
        item_id = loadout_data.get(slot)
        if item_id:
            stats = EQUIPMENT_STATS.get(item_id)
            if stats:
                name = stats["name"]
                val = stats["value"]
                b_type = stats["bonus_type"]
                
                # Add to totals
                if b_type == "xp": total_xp_boost += val
                elif b_type == "loot": total_loot_boost += val
                
                # Format: 💍 Ring: Void Ring (+10% XP)
                bonus_str = f"+{int(val*100)}% {b_type.upper()}"
                icon = "💍" if slot == "Ring" else "🧥" if slot == "Body" else "🧢" if slot == "Head" else "⚔️"
                text_lines.append(f"{icon} **{slot}:** {name} `({bonus_str})`")

    # Footer Stats
    stats_summary = ""
    if total_xp_boost > 0: stats_summary += f"\n✨ **Permanent XP Bonus:** +{int(total_xp_boost*100)}%"
    if total_loot_boost > 0: stats_summary += f"\n🍀 **Permanent Loot Bonus:** +{int(total_loot_boost*100)}%"

    await update.message.reply_text(
        f"**⚔️ CURRENT LOADOUT ⚔️**\n\n" + 
        "\n".join(text_lines) + 
        "\n----------------" + 
        stats_summary,
        parse_mode=ParseMode.MARKDOWN
    )






@check_active_status
async def unequip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Removes an item from a specific slot."""
    if not context.args:
        await update.message.reply_text(f"❌ **Usage:** `/unequip <Slot>`\nValid Slots: {', '.join(VALID_SLOTS)}")
        return
        
    target_slot = context.args[0].capitalize()
    if target_slot not in VALID_SLOTS:
        await update.message.reply_text(f"❌ Invalid Slot. Choose: {', '.join(VALID_SLOTS)}")
        return

    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)

    try:
        @firestore.transactional
        def unequip_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            loadout = snapshot.to_dict().get("loadout", {})
            
            item_id = loadout.get(target_slot)
            if not item_id:
                raise ValueError(f"Nothing equipped in **{target_slot}** slot.")
                
            stats = EQUIPMENT_STATS.get(item_id)
            official_name = stats["name"] if stats else item_id
            
            updates = {
                f"loadout.{target_slot}": firestore.DELETE_FIELD,
                f"inventory.{official_name}": firestore.Increment(1)
            }
            transaction.update(ref, updates)
            return official_name

        transaction = db.transaction()
        removed_item = unequip_transaction(transaction, user_ref)
        await update.message.reply_text(f"📦 **Unequipped:** {removed_item} returned to inventory.", parse_mode=ParseMode.MARKDOWN)

    except ValueError as e:
        await update.message.reply_text(f"❌ {e}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"Unequip error: {e}")







# --- (Add this to your HELPER FUNCTIONS section, near level_up_guild) ---

async def complete_guild_mission(context: ContextTypes.DEFAULT_TYPE, guild_ref, guild_data, mission_data):
    """
    Handles the completion of a guild-wide mission based on the
    new database structure.
    """
    print(f"Completing guild mission '{mission_data.get('title')}' for guild {guild_ref.id}...")
    
    guild_name = guild_data.get("name", "Your Guild")
    mission_title = mission_data.get("title", "Contract")
    member_ids = guild_data.get("members", {}).keys()

    reward_text = ""
    new_gxp = 0

    # --- 1. Process & Distribute Rewards ---
    try:
        # --- GXP Reward ---
        gxp_reward = int(mission_data.get("rewards_gxp", 0))
        if gxp_reward > 0:
            new_gxp += gxp_reward
            reward_text += f"\n• `+{gxp_reward:,}` Guild XP"
            
        # --- Item Rewards (from map) ---
        items_to_give_map = mission_data.get("rewards_items", {})
        
        if items_to_give_map:
            # We need to pre-fetch item data to get official names
            all_items_docs = db.collection("items").stream()
            item_db_lookup = {doc.id: doc.to_dict()["name"] for doc in all_items_docs}
            
            for item_name_key, amount in items_to_give_map.items():
                item_doc_id = item_name_key.lower().replace(' ', '_')
                official_item_name = item_db_lookup.get(item_doc_id, item_name_key) # Fallback to key
                
                item_amount = int(amount)
                if item_amount <= 0: continue

                reward_text += f"\n• `{item_amount}x {official_item_name}` (for all members)"
                
                # Give item to each member
                for user_id in member_ids:
                    user_ref = db.collection("users").document(user_id)
                    user_ref.update({
                        f"inventory.{official_item_name}": firestore.Increment(item_amount)
                    })
                    await asyncio.sleep(0.1) # Avoid spamming Firestore

    except Exception as e:
        print(f"Error distributing guild mission rewards: {e}")

    # --- 2. Broadcast Success Message ---
    broadcast_message = (
        f"**GUILD CONTRACT COMPLETE!** ⚔️\n\n"
        f"Your guild, **{guild_name}**, has successfully completed the contract:\n"
        f"**'{mission_title}'**\n\n"
        f"**REWARDS DISTRIBUTED:**"
        f"{reward_text if reward_text else ' None'}\n\n"
        f"*A new contract is now available. Well done, Hunters.*"
    )
    
    asyncio.create_task(broadcast_to_guild(
        context, 
        member_ids, 
        broadcast_message
    ))

    # --- 3. Clear Active Mission & Update GXP ---
    guild_ref.update({
        "active_mission": firestore.DELETE_FIELD,
        "xp": firestore.Increment(new_gxp)
    })

    # --- 4. Manually Check for Guild Level Up ---
    await asyncio.sleep(1.0) # Give increment time to process
    updated_guild_doc = guild_ref.get()
    if updated_guild_doc.exists:
        await level_up_guild(guild_ref, updated_guild_doc.to_dict(), context)





# --- (Add this to your HELPER FUNCTIONS section) ---

async def level_up_guild(guild_ref, guild_data, context):
    """
    Handles the logic for leveling up a guild.
    Returns the new level, or None if no level-up occurred.
    """
    current_level = guild_data.get('level', 1)
    current_xp = guild_data.get('xp', 0)
    xp_to_next = guild_data.get('xp_to_next_level', GUILD_XP_PER_LEVEL_BASE)

    if current_xp < xp_to_next:
        return None  # Not enough XP, no level up

    # --- Level Up Occurred ---
    new_level = current_level + 1
    xp_overflow = current_xp - xp_to_next
    
    # Calculate XP for the *next* level
    new_xp_to_next = int(xp_to_next * GUILD_LEVEL_MULTIPLIER)

    update_data = {
        "level": new_level,
        "xp": xp_overflow,
        "xp_to_next_level": new_xp_to_next
    }

    # --- Check for New Perks ---
    new_perk = GUILD_PERK_MILESTONES.get(new_level)
    if new_perk:
        update_data["active_perks"] = firestore.ArrayUnion([new_perk["description"]])
        update_data["perk_effects"] = firestore.ArrayUnion([new_perk["effect"]])

    # Atomically update the guild
    guild_ref.update(update_data)

    # --- Broadcast to Guild Members ---
    guild_name = guild_data.get('name', 'Your Guild')
    perk_message = f"\n\n**NEW PERK UNLOCKED:** {new_perk['description']}" if new_perk else ""
    
    broadcast_message = (
        f"**GUILD LEVEL UP!** ⚔️\n\n"
        f"Your guild, **{guild_name}**, has reached **Level {new_level}**!"
        f"{perk_message}\n\n"
        f"*Your combined efforts are paying off. Keep grinding!*"
    )
    
    # Fire and forget the broadcast
    asyncio.create_task(broadcast_to_guild(
        context, 
        guild_data.get("members", {}).keys(), 
        broadcast_message
    ))

    return new_level








# --- (Add these to your HELPER FUNCTIONS section) ---

async def find_user_by_username(search_term: str):
    """
    Smart Search: Looks for a user by Player Name OR Telegram Username OR User ID.
    """
    clean_term = search_term.replace("@", "").strip()
    clean_term_lower = clean_term.lower()
    
    # 1. Try searching by "Player Name" (the 'username' field in DB)
    # This matches the name they chose during onboarding
    query_1 = db.collection("users").where(
        filter=FieldFilter("username", "==", clean_term_lower)
    ).limit(1).stream()
    result = next(query_1, None)
    
    if result:
        return result

    # 2. If not found, try searching by Telegram Username ('username_initial')
    # This matches their actual @TelegramHandle
    query_2 = db.collection("users").where(
        filter=FieldFilter("username_initial", "==", clean_term) 
    ).limit(1).stream()
    result = next(query_2, None)
    
    if result:
        return result

    # 3. If input is a number, try searching by Telegram User ID
    if clean_term.isdigit():
        doc = db.collection("users").document(clean_term).get()
        if doc.exists:
            return doc

    return None

async def find_item_by_name(item_name: str):
    """Fetches an item's data from the 'items' collection by its name."""
    item_doc_id = item_name.lower().replace(' ', '_')
    item_doc = db.collection("items").document(item_doc_id).get()
    if item_doc.exists:
        return item_doc.to_dict() # Return the item's data
    return None # Not found

# --- (Replace your old broadcast_to_all helper function) ---

async def broadcast_to_all(context: ContextTypes.DEFAULT_TYPE, message: str, update: Update):
    """
    Sends a message to ALL users in the database.
    Reports back to the admin who initiated the broadcast upon completion.
    """
    all_users_stream = db.collection("users").stream()
    admin_chat_id = update.effective_chat.id
    
    print("--- STARTING GLOBAL BROADCAST ---")
    count = 0
    errors = 0
    
    for user_doc in all_users_stream:
        user_id = user_doc.id
        if user_id == str(admin_chat_id): # Don't send to the admin twice
            count += 1
            continue
            
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=message, 
                parse_mode=ParseMode.MARKDOWN
            )
            count += 1
            await asyncio.sleep(0.3) # 300ms delay to avoid rate limits
        except Forbidden:
            print(f"  [Fail] User {user_id} has blocked the bot.")
            errors += 1
        except Exception as e:
            print(f"  [Error] Failed to send to {user_id}: {e}")
            errors += 1
            
    print(f"--- BROADCAST COMPLETE --- Sent to {count} users. Failed for {errors} users. ---")
    
    # --- [NEW] Send completion report back to the admin ---
    try:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=f"✅ **System Broadcast Complete**\n\nDecree sent to `{count}` Hunters.\nFailed to reach `{errors}` Hunters."
        )
    except Exception as e:
        print(f"Error sending broadcast report to admin: {e}")



async def broadcast_to_guild(context: ContextTypes.DEFAULT_TYPE, member_ids: list, message: str):
    """
    Sends a message to all member IDs in a list.
    Includes a small delay to avoid rate-limiting.
    """
    for user_id in member_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=message, 
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(0.3) # 300ms delay
        except Forbidden:
            print(f"Warning: Could not DM user {user_id} (bot blocked or left).")
        except Exception as e:
            print(f"Error broadcasting to user {user_id}: {e}")





# --- IMAGE GENERATION ---
def generate_after_action_report(mission_title, xp_reward, old_level, new_level, loot_reward, perks_reward):
    """Generates a comprehensive report card for mission completion."""
    width, height = 800, 450
    card = Image.new("RGB", (width, height), color=(15, 18, 28))
    draw = ImageDraw.Draw(card)

    try:
        font_header = ImageFont.truetype(FONT_FILE_BOLD, 28)
        font_subheader = ImageFont.truetype(FONT_FILE_REGULAR, 24)
        font_main = ImageFont.truetype(FONT_FILE_REGULAR, 22)
        font_title = ImageFont.truetype(FONT_FILE_BOLD, 32)
    except IOError:
        print("Warning: Font files not found. Using default font.")
        font_header = font_subheader = font_main = font_title = ImageFont.load_default()

    draw.rectangle([0, 0, 800, 60], fill=(25, 28, 42))
    draw.text((25, 15), "SYSTEM // AFTER-ACTION REPORT", fill=(200, 200, 255), font=font_subheader)
    draw.text((30, 80), "OBJECTIVE COMPLETE:", fill=(180, 180, 180), font=font_main)
    draw.text((30, 110), f"'{mission_title}'", fill=(230, 230, 230), font=font_title)
    draw.line([400, 170, 400, 420], fill=(50, 55, 70), width=2)
    draw.text((30, 170), "STAT-FEEDBACK:", fill=(200, 200, 255), font=font_subheader)
    draw.text((30, 220), f"✨ XP Gained: +{xp_reward}", fill=(255, 200, 100), font=font_main)
    
    if new_level > old_level:
        draw.text((30, 260), f"🧬 Level: {old_level} ➔ {new_level}", fill=(150, 255, 150), font=font_main)
        draw.rectangle([30, 300, 370, 350], fill=(100, 255, 100))
        draw.text((110, 305), "LEVEL UP!", fill="black", font=font_header)
    else:
        draw.text((30, 260), f"🧬 Level: {new_level}", fill="white", font=font_main)

    draw.text((430, 170), "ASSETS ACQUIRED:", fill=(200, 200, 255), font=font_subheader)
    loot_text = ", ".join(loot_reward) if loot_reward else "None"
    perks_text = ", ".join(perks_reward) if perks_reward else "None"
    draw.text((430, 220), f"🎁 Loot:", fill=(150, 255, 150), font=font_main)
    draw.text((450, 250), loot_text, fill="white", font=font_main)
    draw.text((430, 310), f"💠 Perks:", fill=(150, 200, 255), font=font_main)
    draw.text((450, 340), perks_text, fill="white", font=font_main)

    path = "after_action_report.png"
    card.save(path)
    return path


# --- (Add this to your IMAGE GENERATION section) ---

def generate_profile_card(user_data):
    """Generates a dynamic, premium 'Hunter ID' card."""
    width, height = 800, 450
    
    # --- Base Card & Background ---
    try:
        # You can create a specific 'id_card_bg.jpg' or reuse the profile background
        card = Image.open("profile_background.png").resize((width, height))
    except FileNotFoundError:
        print("Warning: 'profile_background.png' not found. Using default color.")
        card = Image.new("RGB", (width, height), color=(18, 20, 30))

    # Dark overlay for text readability
    overlay = Image.new('RGBA', card.size, (0, 0, 0, 180)) # 180 alpha overlay
    card = Image.alpha_composite(card.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(card, 'RGBA')

    # --- Fonts ---
    try:
        font_header = ImageFont.truetype(FONT_FILE_BOLD, 42)
        font_player_name = ImageFont.truetype(FONT_FILE_BOLD, 36)
        font_rank = ImageFont.truetype(FONT_FILE_BOLD, 72)
        font_label = ImageFont.truetype(FONT_FILE_REGULAR, 20)
        font_data = ImageFont.truetype(FONT_FILE_BOLD, 22)
    except IOError:
        print("Warning: Font files not found. Using default.")
        font_header = font_player_name = font_rank = font_label = font_data = ImageFont.load_default()

    # --- Extract Data ---
    player_name = user_data.get("player_name", "Unknown")
    rank = user_data.get("rank", "E")
    level = user_data.get("level", 1)
    user_id = user_data.get("telegram_id", "N/A") # We pass this in from the profile command
    
    activated_at = user_data.get("activated_at")
    join_date = activated_at.strftime("%Y-%m-%d") if isinstance(activated_at, datetime) else "Unknown"
    
    primary_aim = user_data.get("primary_aim", "Not Specified")
    # Clean up aim text (remove emoji)
    if " " in primary_aim:
        primary_aim = primary_aim.split(" ", 1)[-1] 

    guild_id = user_data.get("guild_id")
    guild_tag = "N/A"
    if guild_id:
        try:
            guild_doc = db.collection("guilds").document(guild_id).get()
            if guild_doc.exists:
                guild_tag = guild_doc.to_dict().get("tag", "???")
        except Exception as e:
            print(f"Error fetching guild tag for profile card: {e}")
            guild_tag = "ERR"
            
    # --- Draw Header ---
    draw.text((40, 30), "SHADOWGRIND PROTOCOL", fill=(150, 150, 170), font=font_label)
    draw.text((40, 55), "HUNTER IDENTIFICATION", fill="white", font=font_header)
    
    # --- Draw Rank (Right Side) ---
    draw.rectangle([580, 120, 760, 300], outline=(200, 200, 255, 100), width=2, fill=(15, 18, 28, 200))
    # Center the Rank text
    rank_text = f"{rank}"
    _, _, w, h = draw.textbbox((0, 0), rank_text, font=font_rank)
    draw.text((580 + (180 - w) / 2, 120 + (180 - h) / 2 - 20), rank_text, fill=(255, 220, 100), font=font_rank) # Gold
    
    # Center the Level text below it
    level_text = f"LEVEL {level}"
    _, _, w_lvl, h_lvl = draw.textbbox((0, 0), level_text, font=font_data)
    draw.text((580 + (180 - w_lvl) / 2, 230), level_text, fill="white", font=font_data)

    # --- Draw Info (Left Side) ---
    y_pos = 150
    
    # Player Name
    draw.text((40, y_pos), "PLAYER NAME", fill=(180, 180, 180), font=font_label)
    y_pos += 30
    draw.text((40, y_pos), f"@{player_name}", fill="white", font=font_player_name)
    y_pos += 60
    
    # Adventure ID (User ID)
    draw.text((40, y_pos), "ADVENTURER ID", fill=(180, 180, 180), font=font_label)
    y_pos += 30
    draw.text((40, y_pos), f"{user_id}", fill="white", font=font_data)
    y_pos += 50
    
    # Columns for smaller data
    x_col1 = 40
    x_col2 = 300
    y_pos_col = y_pos

    # Join Date
    draw.text((x_col1, y_pos_col), "AWAKENED", fill=(180, 180, 180), font=font_label)
    draw.text((x_col1, y_pos_col + 25), join_date, fill="white", font=font_data)
    
    # Guild
    draw.text((x_col2, y_pos_col), "GUILD", fill=(180, 180, 180), font=font_label)
    draw.text((x_col2, y_pos_col + 25), f"[{guild_tag}]", fill="white", font=font_data)
    
    # Primary Aim
    y_pos_col += 70
    draw.text((x_col1, y_pos_col), "PRIMARY AIM", fill=(180, 180, 180), font=font_label)
    # Wrap text in case it's long
    wrapped_aim = textwrap.wrap(primary_aim, width=40)
    for i, line in enumerate(wrapped_aim):
        draw.text((x_col1, y_pos_col + 25 + (i * 22)), line, fill="white", font=font_data)

    # --- Save Image ---
    card = card.convert('RGB')
    path = "hunter_id_card.png"
    card.save(path, "JPEG", quality=85) # Save as compressed JPEG
    return path



def generate_health_bar(current_health, max_health, width=600, height=50):
    """Generates a simple health bar image."""
    health_percentage = current_health / max_health if max_health > 0 else 0
    bar_image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(bar_image)
    draw.rectangle([0, 0, width, height], fill="gray")
    fill_width = int(width * health_percentage)
    draw.rectangle([0, 0, fill_width, height], fill="red")
    return bar_image




# --- (Replace your old generate_guild_card function) ---

# --- (Replace your generate_guild_card function with this one) ---

def generate_guild_card(guild_data):
    """Generates an epic, dynamic 'Guild Banner' image card."""
    width, height = 800, 450 # Made it a bit taller
    
    # --- Base Card & Background ---
    try:
        # Use a generic background, or you could make it dynamic based on guild level
        # --- FIX: Removed "assets/" prefix ---
        card = Image.open("guild_bg.jpg").resize((width, height))
    except FileNotFoundError:
        print("Warning: 'guild_bg.jpg' not found. Using default color.")
        card = Image.new("RGB", (width, height), color=(10, 10, 20))

    # Dark overlay for text readability
    overlay = Image.new('RGBA', card.size, (0, 0, 0, 170)) # 170 alpha overlay
    card = Image.alpha_composite(card.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(card, 'RGBA')

    # --- Fonts ---
    try:
        # --- FIX: Removed "assets/" prefix and used the constants directly ---
        font_guild_name = ImageFont.truetype(FONT_FILE_BOLD, 52)
        font_header = ImageFont.truetype(FONT_FILE_BOLD, 22)
        font_main = ImageFont.truetype(FONT_FILE_REGULAR, 20)
        font_perk = ImageFont.truetype(FONT_FILE_REGULAR, 18)
        font_tag = ImageFont.truetype(FONT_FILE_BOLD, 70)
        font_level = ImageFont.truetype(FONT_FILE_BOLD, 40)
        font_xp = ImageFont.truetype(FONT_FILE_REGULAR, 16)
    except IOError:
        print("Warning: Font files not found. Using default.")
        font_guild_name = font_header = font_main = font_perk = font_tag = font_level = font_xp = ImageFont.load_default()

    # --- Guild Name & Tag ---
    name = guild_data.get('name', 'Unknown Guild')
    tag = guild_data.get('tag', '???')
    draw.rectangle([0, 30, width, 100], fill=(0, 0, 0, 120))
    draw.text((30, 35), name, fill="white", font=font_guild_name)
    
    # --- Guild Emblem/Tag (Right Side) ---
    tag_box_x = 580
    tag_box_y = 120
    draw.rectangle(
        [tag_box_x, tag_box_y, tag_box_x + 180, tag_box_y + 180], 
        outline=(200, 200, 255, 100), 
        width=2, 
        fill=(15, 18, 28, 200)
    )
    # Center the tag text
    _, _, w, h = draw.textbbox((0, 0), f"[{tag}]", font=font_tag)
    draw.text((tag_box_x + (180 - w) / 2, tag_box_y + (180 - h) / 2 - 10), f"[{tag}]", fill="white", font=font_tag)

    # --- Guild Info (Left Side) ---
    y_pos = 150
    draw.text((40, y_pos), "LEADER", fill=(180, 180, 180), font=font_header)
    draw.text((180, y_pos), f"@{guild_data.get('leader_name', 'N/A')}", fill="white", font=font_main)
    y_pos += 40
    
    draw.text((40, y_pos), "MEMBERS", fill=(180, 180, 180), font=font_header)
    draw.text((180, y_pos), f"{guild_data.get('member_count', 0)} / {MAX_GUILD_MEMBERS}", fill="white", font=font_main)
    y_pos += 40
    
    # --- NEW: Guild Level Display ---
    level = guild_data.get('level', 1)
    draw.text((40, y_pos), "LEVEL", fill=(180, 180, 180), font=font_header)
    draw.text((180, y_pos - 5), f"{level}", fill=(255, 220, 100), font=font_level) # Gold color
    y_pos += 60 # More space for XP bar

    # --- NEW: Guild XP Bar ---
    xp = guild_data.get('xp', 0)
    xp_next = guild_data.get('xp_to_next_level', 1)
    xp_percent = 0.0
    if xp_next > 0: # Avoid division by zero
        xp_percent = max(0, min(1, xp / xp_next))
    
    bar_x, bar_y, bar_width, bar_height = 40, y_pos, 500, 25
    fill_width = int(bar_width * xp_percent)
    
    # Draw bar background
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill=(10, 10, 20), outline=(80, 80, 100), width=1)
    # Draw bar fill
    draw.rectangle([bar_x, bar_y, bar_x + fill_width, bar_y + bar_height], fill=(150, 200, 255)) # Light blue fill
    
    # Draw XP Text
    xp_text = f"GXP: {xp:,} / {xp_next:,}"
    _, _, w, h = draw.textbbox((0, 0), xp_text, font=font_xp)
    draw.text((bar_x + (bar_width - w) / 2, bar_y + (bar_height - h) / 2 - 2), xp_text, fill="black", font=font_xp)
    y_pos += bar_height + 25

    # --- NEW: Active Perks Display ---
    draw.text((40, y_pos), "ACTIVE GUILD PERKS:", fill=(200, 200, 255), font=font_header)
    y_pos += 35
    
    active_perks = guild_data.get('active_perks', [])
    if not active_perks:
        draw.text((40, y_pos), "• None. Level up to unlock.", fill=(100, 100, 100), font=font_perk)
    else:
        for perk_desc in active_perks:
            if y_pos < height - 30: # Don't draw off the card
                draw.text((40, y_pos), f"💠 {perk_desc}", fill=(150, 255, 150), font=font_perk) # Greenish tint
                y_pos += 25

    # --- Save Image ---
    card = card.convert('RGB')
    path = "guild_card.png"
    card.save(path, "JPEG", quality=85) # Save as compressed JPEG
    return path



# (Replace your existing generate_mission_card function with this one)

# (Replace your existing generate_mission_card function with this one)

def generate_mission_card(mission_data):
    """Generates a premium, compressed mission card."""
    width, height = 800, 550
    card = Image.new("RGB", (width, height), (15, 18, 28))
    # No Draw object needed as we are not writing text anymore

    mission_type = mission_data.get("type", "All-Round").lower()
    
    # --- 1. Dynamic Background ---
    try:
        bg_path = f"bg_{mission_type}.png" # It can still load a PNG background
        bg_image = Image.open(bg_path).convert("RGB") # Convert to RGB for JPEG saving
        
        # Resize the background image to match the card's dimensions.
        bg_image = bg_image.resize((width, height))
        
        card.paste(bg_image, (0, 0))
        
    except FileNotFoundError:
        print(f"Warning: Background image '{bg_path}' not found. Using default dark color.")

    # --- 2. Save as a compressed JPEG ---
    path = "mission_card.jpg" # Use .jpg extension
    # The 'quality' setting is the key to compression. 85 is a great balance.
    card.save(path, "JPEG", quality=85) 
    return path


def generate_leaderboard_banner(top_hunter):
    """Generates a visual banner for the top-ranked hunter."""
    width, height = 800, 300
    card = Image.new("RGB", (width, height), (15, 18, 28))
    draw = ImageDraw.Draw(card)

    try:
        font_header = ImageFont.truetype(FONT_FILE_BOLD, 48)
        font_sub = ImageFont.truetype(FONT_FILE_REGULAR, 24)
        font_rank = ImageFont.truetype(FONT_FILE_BOLD, 60)
    except IOError:
        font_header = font_sub = font_rank = ImageFont.load_default()

    try:
        bg = Image.open("leaderboard_banner_bg.png").resize((width, height)).convert("RGB")
        card.paste(bg, (0, 0))
    except FileNotFoundError:
        pass

    overlay = Image.new('RGBA', card.size, (0, 0, 0, 100))
    card.paste(overlay, (0, 0), overlay)

    draw.text((40, 40), "THE MONARCH", fill="white", font=font_header)
    draw.text((40, 110), f"@{top_hunter.get('username', 'N/A')}", fill=(200, 200, 255), font=font_sub)
    rank_text = f"Rank {top_hunter.get('rank', 'E')}"
    level_text = f"Level {top_hunter.get('level', 1)}"
    draw.text((width - 300, 100), rank_text, fill=(255, 220, 100), font=font_rank)
    draw.text((width - 300, 170), level_text, fill=(150, 255, 150), font=font_sub)

    path = "leaderboard_banner.png"
    card.save(path)
    return path




# --- (Replace your old generate_inventory_card function) ---

# --- (Replace your old generate_inventory_card function) ---

# --- (Replace your generate_inventory_card function with this one) ---

def generate_inventory_card(user_inventory, db_client):
    """Generates a premium, visual inventory card."""
    
    # --- 1. Define Rarity Visuals ---
    RARITY_COLORS = {
        "Common": (220, 220, 220), # Off-white
        "Rare": (100, 150, 255),   # Bright Blue
        "Epic": (200, 100, 255),   # Purple
        "Legendary": (255, 220, 100) # Gold
    }
    RARITY_EMOJI = {"Common": "⚪️", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
    UNKNOWN_COLOR = (255, 100, 100) # Red for outdated items

    # --- 2. Dynamic Card Sizing ---
    item_count = sum(1 for count in user_inventory.values() if count > 0)
    width = 800
    height = 150 # Base height for header
    
    # Estimate height for each item (varies by description length)
    # We'll fetch the data first to get an accurate height
    
    # --- 3. Pre-fetch Item Data (Fixes Timeout Bug) ---
    all_items_docs = db_client.collection("items").stream()
    item_db_lookup = {}
    for doc in all_items_docs:
        item_db_lookup[doc.id] = doc.to_dict()

    # --- 4. Pre-calculate Text and Height ---
    # This is a bit complex, but it's the only way to get a dynamic height
    # We'll store the lines to draw in a list first
    draw_list = []
    temp_font_desc = ImageFont.truetype(FONT_FILE_REGULAR, 18)
    
    for item_name, count in user_inventory.items():
        if count <= 0: continue
        
        item_doc_id = item_name.lower().replace(' ', '_')
        item_data = item_db_lookup.get(item_doc_id)
        
        item_entry = {"name": f"{item_name} (x{count})"} # Default
        
        if item_data:
            rarity = item_data.get("rarity", "Common")
            item_entry["name"] = f"{RARITY_EMOJI.get(rarity, '⚫️')} {item_name} (x{count})"
            item_entry["color"] = RARITY_COLORS.get(rarity, "Common")
            item_entry["type"] = f"Type: {item_data.get('type', 'Item')}"
            
            desc = item_data.get('description', 'No description.')
            desc_lines = textwrap.wrap(f"Description: {desc}", width=70)
            item_entry["description"] = desc_lines
            
            # Calculate height for this item
            height += 40 # For item name
            height += 30 # For type
            height += (len(desc_lines) * 22) # 22px per description line
            height += 25 # Padding
            
        else:
            # Outdated item
            item_entry["name"] = f"❓ {item_name} (x{count})"
            item_entry["color"] = UNKNOWN_COLOR
            item_entry["type"] = "Type: [Unknown/Outdated Item]"
            item_entry["description"] = []
            height += 100 # Fixed height for unknown items
            
        draw_list.append(item_entry)
        
    height = max(600, height) # Minimum height of 600

    # --- 5. Setup Card and Background ---
    card = Image.new("RGB", (width, height), (15, 18, 28))
    
    try:
        # --- [NEW] Add a background image ---
        bg = Image.open("inventory_bg.jpg").resize(card.size)
        card.paste(bg, (0, 0))
    except FileNotFoundError:
        print("Warning: 'inventory_bg.jpg' not found. Using default color.")
        
    # --- [NEW] Add a dark overlay for readability ---
    overlay = Image.new('RGBA', card.size, (0, 0, 0, 200)) # 200 alpha overlay
    card = Image.alpha_composite(card.convert('RGBA'), overlay).convert('RGB')
    
    draw = ImageDraw.Draw(card)

    # --- 6. Load Fonts (after card is setup) ---
    try:
        font_header = ImageFont.truetype(FONT_FILE_BOLD, 36)
        font_item = ImageFont.truetype(FONT_FILE_BOLD, 24) # Bold item name
        font_item_desc = ImageFont.truetype(FONT_FILE_REGULAR, 18)
    except IOError:
        print("Warning: Fonts not found. Using default.")
        font_header = font_item = font_item_desc = ImageFont.load_default()

    # --- 7. Draw Everything ---
    draw.text((40, 30), "🎒 Your Hunter Inventory", fill="white", font=font_header)
    y_position = 100
    
    if not draw_list:
        draw.text((40, y_position), "Your inventory is empty.", fill="gray", font=font_item)
    else:
        for item in draw_list:
            # Draw Item Name (in its rarity color)
            draw.text((40, y_position), item["name"], fill=item["color"], font=font_item)
            y_position += 35
            
            # Draw Type (in gray)
            draw.text((60, y_position), item["type"], fill=(150, 150, 150), font=font_item_desc)
            y_position += 25
            
            # Draw Description lines
            for line in item["description"]:
                draw.text((60, y_position), line, fill=(150, 150, 150), font=font_item_desc)
                y_position += 22 # 22px spacing for desc lines
                
            # Draw separator line
            y_position += 15
            draw.line([40, y_position, width - 40, y_position], fill=(50, 50, 70), width=1)
            y_position += 25 # Padding for next item

    # --- 8. Save Image ---
    file_path = "inventory_card.png"
    card.save(file_path, "JPEG", quality=85)
    return file_path


# --- (Add this new command, perhaps near /start or /help) ---

@check_active_status # Protect the menu itself
async def system_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main System Interface inline menu."""
    await update.message.reply_text(
        SYSTEM_MENU_TEXT,
        reply_markup=generate_main_menu_keyboard()
    )




# (Replace your existing 'start' function with this)
# --- (Corrected /start function with MAIN_REPLY_MARKUP) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initializes the bot, handling new/returning users and setting the main reply keyboard."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    doc = user_ref.get()
    username = update.effective_user.username or f"User_{user_id}" # Fallback username

    # --- Returning User ---
    if doc.exists and doc.to_dict().get("level"): # Check if they completed onboarding/activation
        data = doc.to_dict()
        welcome_text = ""

        # Check expiry status for returning users
        # Provide a default far in the past if 'expires_at' is missing
        expires_at = data.get("expires_at", datetime(1970, 1, 1, tzinfo=timezone.utc))
        if not isinstance(expires_at, datetime): # Ensure it's a datetime object
             expires_at = datetime(1970, 1, 1, tzinfo=timezone.utc) # Fallback if invalid type

        if datetime.now(timezone.utc) < expires_at:
            # Dagger emoji 🗡️
            welcome_text = "\U0001f5e1\ufe0f **System Reconnected.** Welcome back, Hunter. Use the interface below."
        else:
            # Chains emoji ⛓️
            welcome_text = "\u26d3\ufe0f **Contract Expired.** Connection severed. Use the 'Activate' button below to renew."

        # --- FIX: Use the new MAIN_REPLY_MARKUP ---
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_REPLY_MARKUP # Send the main reply keyboard
        )
        # --- End Fix ---

    # --- New User Onboarding ---
    else:
        # White Circle emoji ⚪️
        await update.message.reply_text("\u26aa\ufe0f *Initiating System Synchronization... Standby...*")
        await asyncio.sleep(1.5)

        # Set initial data and start onboarding
        user_ref.set({
            "telegram_id": user_id,
            "username_initial": username,
            "onboarding_step": "real_name", # Use a dedicated field for onboarding step
            "state": "in_onboarding" # General state for the handler
            }, merge=True)

        await update.message.reply_text(
            "Welcome Candidate.\n\n"
            "To synchronize with the ShadowGrind System, we require some basic data.\n\n"
            "First, please provide your **Real Full Name**."
            # No reply_markup here during onboarding
        )
        # The MAIN_REPLY_MARKUP will appear after onboarding is complete
        # and the user activates or uses /start again.


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides a comprehensive list of available commands."""
    help_text = (
        "📖 **SYSTEM COMMAND MANUAL** 📖\n\n"
        
        "**Core Protocol**\n"
        "`/start` - Initialize contact.\n"
        "`/mission` - Request a new objective.\n"
        "`/complete <proof>` - Submit mission evidence.\n"
        "`/profile` - View Hunter ID & Stats.\n"
        "`/daily` - Claim daily supplies & streak.\n"
        "`/status` - Check contract expiry.\n"
        "`/leaderboard` - View top Hunters.\n\n"

        "**Inventory & Economy**\n"
        "`/inventory` - View your bag (Consumables & Gear).\n"
        "`/use <item>` - Consume an item for a buff.\n"
        "`/blackmarket` - Browse player listings.\n"
        "`/sell <item> <price>` - List item for sale.\n"
        "`/buy <item>` - Purchase an item.\n"
        "`/what` - List sellable assets.\n\n"

        "**The Armory (Equipment)**\n"
        "`/loadout` - View equipped gear & bonuses.\n"
        "`/equip <item>` - Wear a piece of equipment.\n"
        "`/unequip <slot>` - Remove gear.\n\n"

        "**The Forge (Crafting)**\n"
        "`/recipes` - View available blueprints.\n"
        "`/craft <item>` - Create items from materials.\n\n"

        "**Shadow Regiment**\n"
        "`/regiment` - View your shadow army.\n\n"

        "**Guild Operations**\n"
        "`/guild_hall` - Access Guild HQ (Main Hub).\n"
        "`/guild_create` - Form a new guild.\n"
        "`/guild_leave` - Leave current guild.\n"
        "_(Leader/Officer Only)_\n"
        "`/guild_invite @user` - Recruit a Hunter.\n"
        "`/guild_kick @user` - Expel a member.\n"
        "`/guild_promote_officer` - Promote to Officer.\n"
        "`/guild_mission_start` - Activate Guild Contract.\n"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the activation process."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_ref.set({"state": "awaiting_code", "username": update.effective_user.username}, merge=True)
    message = update.message or update.callback_query.message
    await message.reply_text("🗝️ Enter your activation code now.")

# ... (Rest of the bot logic, corrected and integrated)
# --- (The rest of the file follows, with all other functions)

# --- MISSION & PROGRESSION SYSTEM ---
@check_active_status
async def mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates and assigns a new premium mission to the user (Checks Queue first)."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    message = update.callback_query.message if update.callback_query else update.message

    if not user_doc.exists or "level" not in user_doc.to_dict():
        await message.reply_text("⚠️ You need to activate your contract first.")
        return

    user_data = user_doc.to_dict()

    if user_data.get("current_mission"):
        await message.reply_text("⚠️ *Mission Already Active!*\nComplete it with `/complete`.", parse_mode=ParseMode.MARKDOWN)
        return

    # Animated Deployment Sequence
    progress_msg = await message.reply_text("🧠 Accessing DarkNet Archives...")
    animation_steps = ["🗂 Retrieving protocols...", "🔍 Scanning assignment...", "📜 *Mission Deployed!*"]
    for step in animation_steps:
        await asyncio.sleep(0.7)
        await progress_msg.edit_text(step, parse_mode=ParseMode.MARKDOWN)

    # ======================================================
    # [NEW EDIT: QUEUE CHECK]
    # ======================================================
    queued_mission = user_data.get("queued_mission")

    if queued_mission:
        # Use the fixed mission chosen by the Monarch
        mission_data = queued_mission
        
        # Remove it from the queue so the next request returns to random
        user_ref.update({"queued_mission": firestore.DELETE_FIELD})
        
        # Set default categories for local logic if they are missing from the queued object
        difficulty = mission_data.get("difficulty", "Special")
        mtype = mission_data.get("type", "Elite")
    else:
        # No queue found - proceed with Random Selection
        difficulty = random.choice(DIFFICULTIES)
        mtype = random.choice(TYPES)
        missions_ref = db.collection("missions").document("MonarchSystem").collection(difficulty).document(mtype).collection("list")
        all_missions = [doc for doc in missions_ref.stream()]
        
        if not all_missions:
            await message.reply_text(f"❌ No missions found for {difficulty} - {mtype}.")
            return

        mission_doc = random.choice(all_missions)
        mission_data = mission_doc.to_dict()

    # ======================================================
    # [REST OF EXISTING CODE]
    # ======================================================

    # --- [UPDATE FOR ANTI-CHEAT START] ---
    # Add difficulty, type, AND the start time
    mission_data["difficulty"] = difficulty
    mission_data["type"] = mtype
    mission_data["started_at"] = datetime.now(timezone.utc)
    # --- [UPDATE END] ---
    
    user_ref.update({"current_mission": mission_data})

    # --- Generate the Premium Card ---
    card_path = None
    try:
        # Call the new streamlined image generator
        card_path = generate_mission_card(mission_data)
        
        # Determine prefix for the caption
        prefix = "SYSTEM OVERRIDE:" if queued_mission else "OBJECTIVE:"
        
        # --- Construct the Detailed Caption Message ---
        caption_text = (
            f"**{prefix} {mission_data.get('title').upper()}**\n\n"
            f"_{mission_data.get('description', 'No description available.')}_\n\n"
            f"--- **REWARDS** ---\n"
            f"✨ XP Yield: `{mission_data.get('xp', 0)}`\n"
            f"🎁 Potential Loot: `{', '.join(mission_data.get('loot', ['None']))}`\n"
            f"💠 Potential Perks: `{', '.join(mission_data.get('perks', ['None']))}`\n\n"
            f"--- **PROOF REQUIRED** ---\n"
            f"📝 `{mission_data.get('proof_type', 'Screenshot/Text')}`\n\n"
            f"To complete this mission, type `/complete` followed by your proof or media."
        )
        
        with open(card_path, "rb") as photo:
            await message.reply_photo(photo=photo, caption=caption_text, parse_mode=ParseMode.MARKDOWN)
        
        # Send the lore bubble
        await send_mission_lore(update, context, mission_data)

    except Exception as e:
        print(f"Error generating or sending mission card: {e}")
    finally:
        if card_path and os.path.exists(card_path):
            os.remove(card_path)
    
    # Send the voice note as a separate message
    voice_path = "mission_voice.ogg"
    if os.path.exists(voice_path):
        with open(voice_path, "rb") as voice_file:
            await message.reply_voice(voice=voice_file)

    # Delete the "Deploying..." message for a clean chat
    await progress_msg.delete()


@check_active_status
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim daily rewards and build a login streak."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    user_data = user_doc.to_dict()
    
    # 1. Check Timestamps
    last_daily = user_data.get("last_daily")
    now = datetime.now(timezone.utc)
    
    if last_daily:
        # Ensure timezone awareness
        if last_daily.tzinfo is None:
            last_daily = last_daily.replace(tzinfo=timezone.utc)
            
        time_since_last = now - last_daily
        
        # A. Too Early (Less than 24 hours)
        if time_since_last < timedelta(hours=24):
            next_available = last_daily + timedelta(hours=24)
            # Convert to IST for display (UTC+5:30)
            next_available_ist = next_available + timedelta(hours=5, minutes=30)
            time_str = next_available_ist.strftime("%I:%M %p")
            
            await update.message.reply_text(
                f"⏳ **Daily Reward Locked**\n\n"
                f"You have already claimed your supplies for today.\n"
                f"Next Drop: `{time_str}`"
            )
            return

        # B. Missed a Day (More than 48 hours) -> Reset Streak
        if time_since_last > timedelta(hours=48):
            streak = 1
            streak_status = "⚠️ **Streak Lost...** (Starting Over)"
        else:
            # C. Streak Continues
            current_streak = user_data.get("daily_streak", 0)
            streak = current_streak + 1
            streak_status = f"🔥 **Streak Active:** {streak} Days"
    else:
        # First time ever
        streak = 1
        streak_status = "✨ **First Login!** Streak Started."

    # 2. Calculate Rewards
    xp_reward = DAILY_BASE_XP + (streak * DAILY_STREAK_BONUS_XP)
    
    # Cap the streak bonus to prevent game-breaking XP (e.g., max 1000 XP)
    if xp_reward > 1000: xp_reward = 1000
    
    items_given = []
    
    # Milestone Check (Every 7 days)
    if streak % 7 == 0:
        items_given.append(DAILY_MILESTONE_ITEM)
        
    # 3. Update Database
    update_data = {
        "last_daily": now,
        "daily_streak": streak,
        "xp": firestore.Increment(xp_reward)
    }
    
    # Add milestone item if earned
    if items_given:
        # Use a transaction-safe way or just update map key directly
        for item in items_given:
            update_data[f"inventory.{item}"] = firestore.Increment(1)
            
    user_ref.update(update_data)
    
    # 4. Check for Level Up (Standard Logic)
    # Fetch fresh data to check totals
    fresh_user_data = user_ref.get().to_dict()
    current_xp = fresh_user_data.get("xp", 0)
    current_level = fresh_user_data.get("level", 1)
    
    new_level = (current_xp // XP_PER_LEVEL) + 1
    level_up_text = ""
    
    if new_level > current_level:
        user_ref.update({"level": new_level})
        level_up_text = f"\n\n🧬 **LEVEL UP!** {current_level} ➔ {new_level}"

    # 5. Send Premium Message
    reward_text = f"💎 **+{xp_reward} XP**"
    if items_given:
        # Fetch pretty name from config if possible
        item_name = CONSUMABLE_EFFECTS.get(DAILY_MILESTONE_ITEM, {}).get("name", DAILY_MILESTONE_ITEM)
        reward_text += f"\n🎁 **Bonus:** {item_name}"
    
    await update.message.reply_text(
        f"🗓️ **DAILY SUPPLY DROP**\n\n"
        f"{streak_status}\n\n"
        f"**Rewards Acquired:**\n"
        f"{reward_text}"
        f"{level_up_text}",
        parse_mode=ParseMode.MARKDOWN
    )



@check_active_status
async def complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the completion of a mission or rank-up trial task."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    if not user_doc.exists or "level" not in user_doc.to_dict():
        await update.message.reply_text("⚠️ You must activate your contract first.")
        return

    user_data = user_doc.to_dict()
    
    # --- 1. EXISTING RANK UP LOGIC (Preserved) ---
    if user_data.get("state") == "in_rank_up_trial":
        mission_log = " ".join(context.args)
        if not mission_log:
            await update.message.reply_text("❌ **TRIAL PROOF REQUIRED**\n*Usage:* `/complete <your summary of the trial task>`", parse_mode=ParseMode.MARKDOWN)
            return
        await process_rank_up_completion(update, context, user_ref, user_data, proof_data=mission_log)
        return

    current_mission_data = user_data.get("current_mission")
    if not current_mission_data:
        await update.message.reply_text("❗ No active mission. Type `/mission` to begin.")
        return

    # --- 🛡️ NEW: TIME CALCULATION START 🛡️ ---
    started_at = current_mission_data.get("started_at")
    minutes_passed = 999 # Safe default if legacy mission (no timer)

    if started_at:
        # Convert Firestore timestamp to Python datetime if needed
        if isinstance(started_at, datetime):
            start_time = started_at
        else:
            start_time = datetime.now(timezone.utc)

        # Ensure timezone awareness
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        time_elapsed = datetime.now(timezone.utc) - start_time
        minutes_passed = time_elapsed.total_seconds() / 60

    # --- 🚨 LAYER 1: THE SPEED TRAP (< 5 Mins) ---
    # Suspiciously fast? Send straight to Audit without blocking.
    if minutes_passed < 5:
        # Pass the minutes_passed to the helper so the Admin sees "Time: 2 mins"
        await trigger_audit(update, context, user_data, current_mission_data, minutes_passed, "🚀 IMPOSSIBLE SPEED")
        return

    # --- 🛡️ LAYER 2: THE TIME GATE (5 - 20 Mins) ---
    # Fast but not instant? Block them until 20 mins.
    MIN_REQUIRED_MINUTES = 20
    if minutes_passed < MIN_REQUIRED_MINUTES:
        time_left = int(MIN_REQUIRED_MINUTES - minutes_passed) + 1
        await update.message.reply_text(
            f"🚫 **SYSTEM DENIAL: TIMELOCK ACTIVE**\n\n"
            f"The System mandates a minimum of `{MIN_REQUIRED_MINUTES}` minutes for this protocol.\n"
            f"You returned in `{int(minutes_passed)}` minutes.\n\n"
            f"⏳ **Try again in `{time_left}` minutes.**",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    # --- 🛡️ TIME CHECK END 🛡️ ---

    proof_type = current_mission_data.get("proof_type", "log")
    
    if proof_type == "log":
        mission_log = " ".join(context.args)
        if not mission_log:
            await update.message.reply_text("❌ **PROOF REQUIRED**\n*Usage:* `/complete <your summary>`", parse_mode=ParseMode.MARKDOWN)
            return
        
        # --- 👁️ LAYER 3: RANDOM AUDIT (20% Chance) ---
        if random.random() < 0.05:
            await trigger_audit(update, context, user_data, current_mission_data, minutes_passed, "🎲 RANDOM CHECK")
            return
        # ---------------------------------------------

        await process_mission_completion(update, context, user_ref, user_data, current_mission_data, proof_data=mission_log)
    
    elif proof_type == "photo":
        user_ref.update({"state": "awaiting_photo_proof"})
        await update.message.reply_text("📸 **PHOTO PROOF REQUIRED**\nPlease send the image now.", parse_mode=ParseMode.MARKDOWN)


# --- (Replace your old process_mission_completion function) ---

async def process_mission_completion(update, context, user_ref, user_data, mission_data, proof_data=None):
    """Central function to handle all post-mission-completion logic with Auto-Fix for XP."""
    # Use effective_message to prevent crashes on edited messages
    message = update.effective_message
    
    is_manual_approval = (update.callback_query and update.callback_query.data.startswith("audit_pass_"))
    
    progress_msg = None
    if not is_manual_approval:
        progress_msg = await message.reply_text("🧬 Accessing Soul Core... Verifying contract fulfillment...")
    
    mission_title = mission_data.get("title", "Unknown Objective")
    xp_reward = mission_data.get("xp", 0)
    perk_reward = mission_data.get("perks", [])
    
    # ======================================================
    # 1. D-RANK XP NERF (50% DAMPENING FIELD)
    # ======================================================
    current_level = user_data.get("level", 1)
    original_base_xp = xp_reward
    summary_text = f"Objective **'{mission_title}'** complete."

    # If Level is 10 or higher (D-Rank+), Reduce XP by 50%
    if current_level >= 10:
        xp_reward = int(xp_reward * 0.5) # <--- The 50% Calculation
        summary_text += f"\n📉 _Dampening Field: XP reduced by 50% ({original_base_xp} ➔ {xp_reward})._"

    # ======================================================
    # 2. BONUS CALCULATION (Guild Perks + Active Items)
    # ======================================================
    guild_id = user_data.get("guild_id")
    guild_perk_effects = []
    guild_ref = None 

    if guild_id:
        guild_ref = db.collection("guilds").document(guild_id)
        guild_doc = guild_ref.get()
        if guild_doc.exists:
            guild_perk_effects = guild_doc.to_dict().get("perk_effects", [])

    # -- Calculate XP Boost --
    xp_boost_total = 1.0
    
    # A. Guild Perks
    for effect in guild_perk_effects:
        if effect.startswith("xp_boost_"):
            try:
                xp_boost_total += float(effect.split('_')[2])
            except: pass

    # B. Active Item Effects
    active_effects = user_data.get("active_effects", {})
    xp_effect = active_effects.get("xp_boost")
    
    item_boost_active = False
    if xp_effect:
        # Check expiry
        expires_at = xp_effect.get("expires_at")
        if expires_at:
            # Timezone fix
            now_utc = datetime.now(timezone.utc)
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at > now_utc:
                # Apply multiplier
                xp_boost_total *= float(xp_effect.get("value", 1.0))
                item_boost_active = True

    # C. Loadout (Equipment) Bonuses
    loadout = user_data.get("loadout", {})
    for slot, item_id in loadout.items():
        stats = EQUIPMENT_STATS.get(item_id)
        if stats and stats.get("bonus_type") == "xp":
            xp_boost_total += stats.get("value", 0.0)
            
    # Apply Total Boost
    final_xp_gain = int(xp_reward * xp_boost_total)

    # -- Summary Text Update --
    if xp_boost_total > 1.0:
        summary_text += f"\n⚡ **XP Boosted!** ({int(xp_boost_total*100 - 100)}% Bonus)"
        if item_boost_active:
            summary_text += f"\n   _(Effect: {xp_effect['source']} active)_"

    # ======================================================
    # 3. LEVEL CALCULATION & LEGACY DATA FIX (THE CRITICAL FIX)
    # ======================================================
    previous_level = user_data.get("level", 1)
    current_total_xp = user_data.get("xp", 0)

    # [AUTO-FIX]: Check if XP is too low for current level (Legacy Data Glitch)
    # E.g. User is Level 9 but has 0 XP. 
    # Minimum XP for Level 9 is 8000. So we bump them to 8000.
    min_xp_for_current_level = get_level_start_xp(previous_level)
    
    if current_total_xp < min_xp_for_current_level:
        current_total_xp = min_xp_for_current_level
        print(f"DEBUG: Fixed Legacy XP for User {user_ref.id}. Bumped to {min_xp_for_current_level}.")

    # Now add the new reward to the FIXED total
    new_total_xp = current_total_xp + final_xp_gain
    
    # Calculate new level based on this correct total using NEW MATH
    new_level = calculate_level_from_xp(new_total_xp)
    
    level_up_occurred = new_level > previous_level
    if level_up_occurred:
        summary_text += f"\n\n**LEVEL UP!** You have ascended to Level {new_level}."
        
        # Add warning if they just hit D-Rank
        if new_level == 10:
            summary_text += "\n\n⚠️ **WARNING: D-RANK REACHED**\nXP Requirement doubled to 2000.\nMission rewards are now capped at 100 XP."

    # ======================================================
    # 4. DATABASE UPDATES
    # ======================================================
    updates = {
        "xp": new_total_xp,  # Save absolute value to prevent future glitches
        "level": new_level,
        "current_mission": firestore.DELETE_FIELD, 
        "state": firestore.DELETE_FIELD
    }
    if perk_reward:
        updates["perks"] = firestore.ArrayUnion(perk_reward)
    user_ref.update(updates)
    
    # Update local data copy for next steps
    user_data['level'] = new_level
    user_data['xp'] = new_total_xp

    
    # [PASTE THIS HERE] GLOBAL AUDIT LOGGING
    # ======================================================
    try:
        # 1. Calculate Time Taken (Duration)
        # We fetch start time from the local user_data BEFORE it was deleted in DB
        start_time = user_data.get("current_mission", {}).get("started_at")
        time_str = "Unknown"
        
        if start_time:
            # Normalize time formats
            if hasattr(start_time, 'timestamp'):
                st = start_time
            elif isinstance(start_time, str):
                try: st = datetime.fromisoformat(start_time)
                except: st = datetime.now(timezone.utc)
            else:
                st = datetime.now(timezone.utc)

            # Ensure Timezone compatibility
            if st.tzinfo is None: st = st.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            
            diff = now - st
            total_seconds = int(diff.total_seconds())
            h, rem = divmod(total_seconds, 3600)
            m, s = divmod(rem, 60)
            time_str = f"{h}h {m}m {s}s"

        # 2. Prepare Log Data
        audit_log = {
            "user_id": user_ref.id,
            "username": user_data.get("username", "Unknown Hunter"),
            "mission_title": mission_title,
            "xp_earned": final_xp_gain,
            "time_taken": time_str,
            "proof_type": mission_data.get("proof_type", "log"),
            "proof_data": proof_data if proof_data else "No Data",
            "completed_at": firestore.SERVER_TIMESTAMP
        }

        # 3. Save to 'mission_logs' collection
        db.collection("mission_logs").add(audit_log)
        print(f"✅ Audit Log Saved for {user_data.get('username')}")
        
    except Exception as e:
        print(f"⚠️ Error logging mission audit: {e}")
    # ======================================================
    # 5. RANK UP CHECK
    # ======================================================
    current_rank = user_data.get("rank", "E")
    next_rank_level_req = RANK_UP_LEVELS.get(current_rank)
    rank_up_eligible = False
    
    if next_rank_level_req:
        if new_level >= next_rank_level_req:
            rank_up_eligible = True
            
    if rank_up_eligible:
        next_rank_letter = chr(ord(current_rank) - 1) if current_rank > "A" else "S"
        
        # Send the Rank-Up Prompt
        rank_up_text = (
            f"**SYSTEM ALERT: RANK QUALIFICATION REACHED**\n\n"
            f"Hunter, your power has surged. You have reached Level `{new_level}` and are now eligible to challenge the trial for **{next_rank_letter}-Rank**.\n\n"
            f"This trial will test your limits. Succeed, and ascend. Fail, and remain.\n\n"
            f"Do you accept the challenge?"
        )
        keyboard = [[
            InlineKeyboardButton(f"⚔️ Begin {next_rank_letter}-Rank Trial", callback_data=f"rankup_accept_{current_rank}"), 
            InlineKeyboardButton("⏳ Prepare Further", callback_data="rankup_decline")
        ]]
        await message.reply_text(rank_up_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        summary_text += f"\n\n**Eligible for {next_rank_letter}-Rank Trial!**"

    # ======================================================
    # 6. LOOT DROP SYSTEM
    # ======================================================
    new_loot = []
    loot_chance = 0.50 
    
    for effect in guild_perk_effects:
        if effect.startswith("loot_boost_"):
            try:
                loot_chance += float(effect.split('_')[2])
            except Exception as e:
                print(f"Error applying loot perk {effect}: {e}")
                
    if random.random() < loot_chance:  
        rarity_map = {"Legendary": 0.05, "Epic": 0.15, "Rare": 0.30, "Common": 1.0}
        rarity_roll = random.random()
        chosen_rarity = "Common"
        if rarity_roll < rarity_map["Legendary"]: chosen_rarity = "Legendary"
        elif rarity_roll < rarity_map["Epic"]: chosen_rarity = "Epic"
        elif rarity_roll < rarity_map["Rare"]: chosen_rarity = "Rare"

        items_query = db.collection("items").where(filter=FieldFilter("rarity", "==", chosen_rarity)).stream()
        items_of_rarity = [doc.to_dict() for doc in items_query]
        
        if items_of_rarity:
            item = random.choice(items_of_rarity)
            item_name = item.get("name")
            user_ref.update({f'inventory.{item_name}': firestore.Increment(1)})
            new_loot.append(item_name)
            
            if chosen_rarity in ["Rare", "Epic", "Legendary"]:
                await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_PHOTO)
                await asyncio.sleep(1.5) 
                await message.reply_photo(photo=SPECIAL_DROP_FILE_ID)
                await message.reply_voice(voice=SUCCESS_VOICE_FILE_ID)
                summary_text += f"\n\n🎉 A **{chosen_rarity}** item has dropped! You acquired: **{item_name}**!"
            else:
                await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_PHOTO)
                await asyncio.sleep(0.5) 
                await message.reply_photo(photo=COMMON_DROP_FILE_ID)
                summary_text += f"\n\n🎁 You acquired a **Common** item: **{item_name}**."

    if not new_loot:
        summary_text += "\n\n😢 No drop this time. Better luck next time!"

    # ======================================================
    # 7. WORLD BOSS LOGIC (MOVED BEFORE GUILD LOGIC)
    # ======================================================
    
    # Initialize Damage Variable (Critical Scope Fix)
    damage_dealt = 0 
    
    active_boss_query = db.collection("world_bosses").where(filter=FieldFilter("is_active", "==", True)).limit(1).stream()
    active_boss_doc = next(active_boss_query, None)
    
    if active_boss_doc:
        damage_dealt = max(1, int(final_xp_gain * 0.01)) 
        user_id_str = str(update.effective_user.id)
        
        # Define transaction for boss
        @firestore.transactional
        def _update_boss(transaction, boss_ref, u_id, dmg):
            snapshot = boss_ref.get(transaction=transaction)
            if not snapshot.exists: return False
            curr_hp = snapshot.get('current_health')
            new_hp = curr_hp - dmg
            upd = {f'damage_log.{u_id}': firestore.Increment(dmg)}
            is_dead = False
            if new_hp <= 0:
                upd['current_health'] = 0
                upd['is_active'] = False
                is_dead = True
            else:
                upd['current_health'] = new_hp
            transaction.update(boss_ref, upd)
            return is_dead

        transaction = db.transaction()
        boss_defeated = _update_boss(transaction, active_boss_doc.reference, user_id_str, damage_dealt)

        if boss_defeated:
            boss_data = active_boss_doc.to_dict()
            winner_name = user_data.get("username", "Unknown")
            vic_msg = (f"**⚔️ VICTORY! ⚔️**\n\n"
                       f"The World Boss **{boss_data['name']}** has been defeated!\n\n"
                       f"**The Monarch's Hand (Final Blow):** @{winner_name}")
            await context.bot.send_message(chat_id=message.chat_id, text=vic_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            summary_text += f"\n⚔️ **World Boss:** You dealt `{damage_dealt}` Damage!"

    # ======================================================
    # 8. GUILD LOGIC (NOW SEES 'damage_dealt')
    # ======================================================
    
    if guild_id and guild_ref:
        # --- 1. Calculate and Give Guild XP (Standard) ---
        gxp_reward = int(original_base_xp * GXP_CONTRIBUTION_RATE) 
        
        # Apply Guild GXP Boosts
        gxp_boost = 1.0
        for effect in guild_perk_effects:
            if effect.startswith("gxp_boost_"):
                try: gxp_boost += float(effect.split('_')[2])
                except: pass
        
        gxp_reward = int(gxp_reward * gxp_boost)
        guild_ref.update({"xp": firestore.Increment(gxp_reward)})
        
        # Check Guild Level Up (Async)
        updated_guild_doc = guild_ref.get()
        if updated_guild_doc.exists:
            await level_up_guild(guild_ref, updated_guild_doc.to_dict(), context)
            
        # --- 2. CHECK ACTIVE GUILD MISSION PROGRESS ---
        guild_data = updated_guild_doc.to_dict()
        active_mission = guild_data.get("active_mission")
        
        if active_mission:
            # We use the 'type' field from the database to decide logic
            m_type = active_mission.get("type", "generic")
            increment_amount = 0
            
            # --- LOGIC MAPPING ---
            
            # 1. "Complete 15 'Advanced' or 'Extreme' missions"
            if m_type == "mission_difficulty_hard":
                p_diff = mission_data.get("difficulty", "Easy")
                if p_diff in ["Advanced", "Extreme"]:
                    increment_amount = 1

            # 2. "Earn 50,000 XP"
            elif m_type == "xp_goal":
                increment_amount = final_xp_gain

            # 3. "Complete 40 'Mental' missions"
            elif m_type == "mission_type_mental":
                if mission_data.get("type") == "Mental":
                    increment_amount = 1

            # 4. "Complete 40 'Physical' missions"
            elif m_type == "mission_type_physical":
                if mission_data.get("type") == "Physical":
                    increment_amount = 1

            # 5. "Complete 75 missions of any type"
            elif m_type == "mission_goal":
                increment_amount = 1

            # 6. "Deal 25,000 damage to World Boss"
            elif m_type == "boss_damage_goal":
                # USES THE 'damage_dealt' VARIABLE CALCULATED ABOVE
                increment_amount = damage_dealt

            # --- 3. APPLY THE UPDATE ---
            if increment_amount > 0:
                current_progress = active_mission.get("current_progress", 0)
                target_goal = active_mission.get("goal", 100)
                
                new_progress = current_progress + increment_amount
                
                # Update DB
                if new_progress >= target_goal:
                    await complete_guild_mission(context, guild_ref, guild_data, active_mission)
                    summary_text += f"\n\n**🎉 Guild Contract Complete!**"
                else:
                    guild_ref.update({
                        "active_mission.current_progress": firestore.Increment(increment_amount)
                    })
                    
                    # Smart Feedback Message
                    if m_type in ["xp_goal", "boss_damage_goal"]:
                        summary_text += f"\n📜 Guild Progress: `+{increment_amount}` ({new_progress:,}/{target_goal:,})"
                    else:
                        summary_text += f"\n📜 Guild Progress: `+1` ({new_progress}/{target_goal})"

    # ======================================================
    # 9. FINAL REPORT & CLEANUP
    # ======================================================
    report_card_path = None
    try:
        # Note: 'new_loot' and 'perk_reward' were defined in earlier blocks
        report_card_path = await generate_after_action_report(
            mission_title, final_xp_gain, previous_level, new_level, new_loot, perk_reward
        )
        if report_card_path and os.path.exists(report_card_path):
            with open(report_card_path, "rb") as photo:
                await message.reply_photo(photo=photo)
    except Exception as e:
        print(f"Error sending AAR: {e}")
    finally:
        if report_card_path and os.path.exists(report_card_path):
            os.remove(report_card_path)

    final_keyboard = [[
        InlineKeyboardButton("📜 New Mission", callback_data="mission"), 
        InlineKeyboardButton("👤 View Profile", callback_data="profile")
    ]]
    await message.reply_text(
        summary_text, 
        reply_markup=InlineKeyboardMarkup(final_keyboard), 
        parse_mode=ParseMode.MARKDOWN
    )
    
    if progress_msg:
        try: await progress_msg.delete()
        except: pass


async def start_rank_up_trial(update: Update, context: ContextTypes.DEFAULT_TYPE, rank: str):
    """Begins the rank-up trial for a user."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    
    quest_tasks = RANK_UP_QUESTS.get(rank)
    if not quest_tasks:
        await update.callback_query.message.reply_text("Error: Trial data not found.")
        return

    trial_data = {"rank_being_trialed": rank, "current_step": 0, "tasks": quest_tasks}
    user_ref.update({"state": "in_rank_up_trial", "rank_up_progress": trial_data})
    
    first_task = quest_tasks[0]
    message = (
        f"**TRIAL - OBJECTIVE 1 of {len(quest_tasks)}**\n\n"
        f"*{first_task['task']}*\n\n"
        f"Submit your proof using the `/complete` command."
    )
    await update.callback_query.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def process_rank_up_completion(update: Update, context: ContextTypes.DEFAULT_TYPE, user_ref, user_data, proof_data):
    """Processes a single step in a rank-up trial."""
    trial_progress = user_data.get("rank_up_progress")
    current_step = trial_progress.get("current_step", 0)
    tasks = trial_progress.get("tasks", [])
    
    next_step = current_step + 1
    
    if next_step < len(tasks):
        user_ref.update({"rank_up_progress.current_step": next_step})
        next_task = tasks[next_step]
        message = (
            f"✅ **Objective {next_step} Complete!**\n\n"
            f"**TRIAL - OBJECTIVE {next_step + 1} of {len(tasks)}**\n\n"
            f"*{next_task['task']}*\n\n"
            f"Submit your proof using `/complete`."
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    else:
        old_rank = trial_progress.get("rank_being_trialed", "E")
        new_rank = chr(ord(old_rank) - 1) if old_rank > "A" else "S"
        
        user_ref.update({
            "rank": new_rank,
            "state": firestore.DELETE_FIELD,
            "rank_up_progress": firestore.DELETE_FIELD
        })
        
        message = (
            f"**⚔️ TRIAL COMPLETE ⚔️**\n\n"
            f"You have shattered your limits and proven your worth.\n\n"
            f"**PROMOTION: {old_rank}-Rank ➔ {new_rank}-Rank**"
        )
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)



# (Replace your entire 'profile' function with this)

# (Replace your entire 'profile' function with this)

@check_active_status
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's premium ID card, badges, and stats with Corrected Math."""
    message = update.effective_message
    user_id = str(update.effective_user.id)
    loading_message = await message.reply_text("🧠 Accessing Hunter Database...")

    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists or "level" not in user_doc.to_dict():
        await loading_message.edit_text("⚠️ You must activate your contract first.")
        return

    user_data = user_doc.to_dict()
    user_data["telegram_id"] = user_id 

    await loading_message.edit_text("📊 Compiling Hunter Record...")

    # --- 1. GET & CORRECT DATA ---
    current_total_xp = user_data.get("xp", 0)
    
    # [THE FIX] Recalculate level on the fly based on Total XP
    # This ensures the level displayed always matches the XP math, fixing glitches.
    level = calculate_level_from_xp(current_total_xp)
    
    # If the calculated level is different from DB, update the variable for display
    # (We don't save to DB here to keep it fast, but it fixes the visual math)
    user_data['level'] = level 
    
    # --- 2. CALCULATE RELATIVE PROGRESS ---
    # How much XP is needed to finish THIS specific level? (1000, 2000, etc.)
    xp_cap_for_this_level = get_xp_req_for_level(level)
    
    # How much Total XP was required to reach the START of this level?
    xp_at_start_of_level = get_level_start_xp(level)
    
    # Subtract previous levels to get current progress bar
    # e.g. 2940 Total - 2000 (Start of Lv 3) = 940 XP Progress
    xp_progress = current_total_xp - xp_at_start_of_level
    
    # Safety catch for legacy data weirdness
    if xp_progress < 0:
        xp_progress = 0 

    # Remaining to next level
    xp_to_next = xp_cap_for_this_level - xp_progress

    # --- 3. FORMATTING ---
    expires_at = user_data.get("expires_at")
    expiry_status = "`Unknown`"
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None: expires_at = expires_at.replace(tzinfo=timezone.utc)
        days_left = (expires_at - datetime.now(timezone.utc)).days
        expiry_status = f"`{days_left}` days remaining" if days_left >= 0 else "`Expired`"
    elif expires_at:
        expiry_status = str(expires_at)

    total_items = sum(count for count in user_data.get("inventory", {}).values() if count > 0)
    try: shadows_count = len(list(user_ref.collection("shadows").stream()))
    except: shadows_count = 0

    # --- [NEW] BADGE DISPLAY LOGIC ---
    # We fetch the stylized badge list using the helper function
    badge_visuals = get_badge_display(user_data, mode="profile")
    
    badge_section = ""
    if badge_visuals:
        badge_section = f"**🏆 ACHIEVEMENTS**\n{badge_visuals}\n\n"

    # --- 4. BUILD CAPTION ---
    profile_caption = (
        f"**📊 SYSTEM STATS & ASSETS**\n\n"
        f"{badge_section}"  # <--- INJECTED BADGES HERE
        f"**Progression**\n"
        f"> 🏆 Level: `{level}`\n"
        f"> ✨ XP: `{xp_progress} / {xp_cap_for_this_level}`\n" 
        f"> 📈 To Level Up: `{xp_to_next}` XP needed\n\n"

        f"**Contract**\n"
        f"> ⏳ Status: {expiry_status}\n\n"

        f"**Assets**\n"
        f"> 🎒 Inventory Items: `{total_items}`\n"
        f"> 👻 Shadow Soldiers: `{shadows_count}`\n"
    )

    # --- 5. SEND ---
    card_path = None
    try:
        card_path = generate_profile_card(user_data)
        with open(card_path, "rb") as photo:
            await message.reply_photo(photo=photo, caption=profile_caption, parse_mode=ParseMode.MARKDOWN)
        await loading_message.delete()
    except Exception as e:
        print(f"Error generating profile: {e}")
        # Fallback to text-only if image generation fails
        await loading_message.edit_text(profile_caption, parse_mode=ParseMode.MARKDOWN)
    finally:
        if card_path and os.path.exists(card_path): os.remove(card_path)



# --- (Corrected /inventory command - Button Aware) ---
@check_active_status
async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's inventory as a detailed text list."""
    user_id = str(update.effective_user.id)
    
    # 1. Fetch Data
    user_doc = db.collection("users").document(user_id).get()
    inventory_map = user_doc.to_dict().get("inventory", {})
    
    # Filter for valid items
    valid_inventory = {k: v for k, v in inventory_map.items() if v > 0}
    
    if not valid_inventory:
        await update.message.reply_text("🎒 **Your inventory is empty.**\n\nComplete missions to earn loot!")
        return

    # 2. Pre-fetch Item Details (Optimization)
    all_items_docs = db.collection("items").stream()
    item_db_lookup = {doc.id: doc.to_dict() for doc in all_items_docs}
    
    # Rarity Visuals
    rarity_emojis = {"Common": "⚪️", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
    
    # 3. Build the Text List
    inventory_text = ""
    total_items = 0
    
    # Sort items alphabetically
    sorted_items = sorted(valid_inventory.items())
    
    for item_key, count in sorted_items:
        total_items += count
        
        # Resolve Data
        doc_id = item_key.lower().replace(" ", "_").replace("'", "'")
        item_data = item_db_lookup.get(doc_id)
        
        official_name = item_data.get("name", item_key) if item_data else item_key
        rarity = item_data.get("rarity", "Common") if item_data else "Common"
        emoji = rarity_emojis.get(rarity, "⚪️")
        
        # Check if Usable (using your Config)
        is_usable = doc_id in CONSUMABLE_EFFECTS
        
        # Format Line
        # Example: 🔵 **Scroll of Insight** (x2) [⚡USE]
        line = f"{emoji} **{official_name}** `(x{count})`"
        if is_usable:
            line += " `[⚡USE]`"
            
        inventory_text += line + "\n"

    # 4. Send Message
    header = f"🎒 **HUNTER INVENTORY ({total_items} Items)**\n\n"
    footer = (
        "\n-----------------------------\n"
        "⚡ **Actions:**\n"
        "• To use an item: `/use <Item Name>`\n"
        "• To sell an item: `/sell <Item Name> <Price>`"
    )
    
    await update.message.reply_text(header + inventory_text + footer, parse_mode=ParseMode.MARKDOWN)


@check_active_status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks the user's subscription status."""
    user_id = str(update.effective_user.id)
    user_doc = db.collection("users").document(user_id).get()

    if not user_doc.exists or "level" not in user_doc.to_dict():
        await update.message.reply_text("🔒 *Unauthorized Access Detected...*", parse_mode=ParseMode.MARKDOWN)
        return

    user_data = user_doc.to_dict()
    expires_at = user_data.get("expires_at", datetime.now(timezone.utc))
    days_left = (expires_at - datetime.now(timezone.utc)).days

    if days_left >= 0:
        await update.message.reply_text(f"🩸 *Grind Protocol Status: ACTIVE*\n⏳ *Time Remaining:* `{days_left}` day(s)", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("⛓️ *Link Severed...*\n\nYour soul contract has expired.", parse_mode=ParseMode.MARKDOWN)




# Helper function to prevent crashes
def escape_markdown(text):
    """Escapes special characters for Telegram Markdown."""
    if not text: return ""
    # Escape: _ * ` [
    return text.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

@check_active_status
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the server-wide leaderboard using Player Names."""
    # 1. Safety Fix: Use effective_message to prevent crashes on edits
    message = update.effective_message
    
    # [YOUR ORIGINAL LOGIC] Collect and Sort
    all_users = [doc.to_dict() for doc in db.collection("users").stream() if doc.to_dict().get("rank")]
    sorted_users = sorted(all_users, key=lambda u: (get_rank_sort_value(u["rank"]), -u["level"]))

    if not sorted_users:
        await message.reply_text("No Hunters have been registered yet. Be the first!")
        return

    top_hunter = sorted_users[0]
    
    # Generate Banner
    banner_path = generate_leaderboard_banner(top_hunter)
    try:
        with open(banner_path, "rb") as photo:
            # [UPDATE] Add Badges to Banner Caption
            top_badges = get_badge_display(top_hunter, mode="inline")
            
            # [CRITICAL FIX] Escape the name to prevent the crash you just had
            raw_name = top_hunter.get("player_name") or top_hunter.get("username", "Unknown")
            safe_top_name = raw_name.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
            
            caption = f"🏆 **#1 SUPREME HUNTER**\n{top_badges}**{safe_top_name}**"
            await message.reply_photo(photo=photo, caption=caption, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"Banner error: {e}")
    finally:
        if os.path.exists(banner_path):
            os.remove(banner_path)

    leaderboard_text = "🏆 **Shadow Hunter Leaderboard** 🏆\n\n"
    
    # 2. Name Fix: Iterate and prioritize 'player_name'
    for i, user in enumerate(sorted_users[1:10], 2):
        # Logic: Try player_name -> Try username -> Default to "Unknown"
        raw_name_display = user.get("player_name") or f"@{user.get('username', 'Unknown')}"
        
        # [CRITICAL FIX] Escape special characters so the bot doesn't crash on names like "Elite_EconomiX"
        name_display = raw_name_display.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
        
        # [UPDATE] Get Badges here
        badges = get_badge_display(user, mode="inline")
        
        # If it's a player name (no @), make it bold.
        # [UPDATE] Added {badges} before the name
        leaderboard_text += f"{i}. {badges}**{name_display}** - Rank **{user.get('rank', 'E')}** (Level {user.get('level', 1)})\n"
        
    await message.reply_text(leaderboard_text, parse_mode=ParseMode.MARKDOWN)
# --- ECONOMY & BLACK MARKET ---

# (Replace your existing 'blackmarket' function with this)

# --- (Corrected /blackmarket command - Button Aware & Optimized) ---
@check_active_status
async def blackmarket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays all items currently for sale on the Black Market. Handles button calls & optimized DB access."""
    # --- Button Handling: Determine chat_id ---
    chat_id_to_use = None
    if update.message: # Called via text command /blackmarket
        chat_id_to_use = update.message.chat_id
    elif update.callback_query: # Called via button press
        chat_id_to_use = update.callback_query.message.chat_id
    if not chat_id_to_use:
        print("Error in /blackmarket: Could not determine chat ID")
        return

    # Send initial loading message as a NEW message
    loading_message = await context.bot.send_message(
        chat_id=chat_id_to_use,
        text="\U0001f4f6 Connecting to the Shadow Network..." # Signal bars emoji 📶
    )
    # --- End Button Handling ---

    try:
        await asyncio.sleep(0.5) # Short pause for effect

        # --- FIX: Fetch all item data ONCE to prevent timeout ---
        all_items_docs = db.collection("items").stream()
        item_db_lookup = {} # Key: lowercase_with_underscores, Value: dict
        for doc in all_items_docs:
            item_data = doc.to_dict()
            item_db_lookup[doc.id] = { # Use doc.id as the key
                "rarity": item_data.get("rarity", "Common"),
                "name": item_data.get("name", doc.id) # Store the proper cased name
            }
        # --- End Fix ---

        # --- Fetch Market Data ---
        market_ref = db.collection("market")
        items_for_sale_query = market_ref.where(filter=FieldFilter("is_sold", "==", False)).stream()
        items_for_sale = list(items_for_sale_query) # Convert stream to list

        if not items_for_sale:
            await loading_message.edit_text(
                "\U0001f3ad The Black Market is currently empty. No items listed for sale." # Performing arts emoji 🎭
            )
            return

        await loading_message.edit_text(
            "\U0001f4ca Compiling market data..." # Bar chart emoji 📊
        )

        # --- Construct Premium Caption ---
        market_text = ""
        # Use Unicode escapes for rarity emojis
        rarity_emojis = {"Common": "\u26aa\ufe0f", "Rare": "\U0001f535", "Epic": "\U0001f7e3", "Legendary": "\U0001f7e1"} # ⚪️🔵🟣🟡

        for item_doc in items_for_sale:
            market_item_data = item_doc.to_dict()
            item_name_from_market = market_item_data.get("item_name", "Unknown Item")

            # --- FIX: Use local item_db_lookup (fast) ---
            item_doc_id = item_name_from_market.lower().replace(' ', '_')
            item_info = item_db_lookup.get(item_doc_id) # Look up using the doc_id format

            item_rarity = "Item"
            official_name = item_name_from_market # Fallback name
            if item_info:
                item_rarity = item_info["rarity"]
                official_name = item_info["name"] # Use the official name from DB
            # --- End Fix ---

            rarity_emoji = rarity_emojis.get(item_rarity, "\u26ab\ufe0f") # Black circle ⚫️ fallback

            market_text += (
                f"{rarity_emoji} **{official_name}** `[{item_rarity}]`\n"
                f"  ID: `{item_doc.id}`\n"  # <--- ADD THIS LINE
                f"  Seller: @{market_item_data.get('seller_username', 'N/A')}\n"
                f"  Price: `\u20B9{market_item_data.get('price', '?')}`\n" # Rupee sign ₹
                f"  To purchase: `/buy \"{official_name}\"`\n\n" # Use official name in buy instruction
            )

        caption_title = "**SHADOW MARKET LISTINGS**\n\n"
        caption_footer = "\n_Use the `/buy` command with the exact item name._"
        full_caption = caption_title + market_text + caption_footer

        # --- Send Themed Image with Caption (as a new message) ---
        try:
            await context.bot.send_photo(
                chat_id=chat_id_to_use,
                photo=BG_BLACKMARKET_FILE_ID, # Assumes this file_id is correct
                caption=full_caption,
                parse_mode=ParseMode.MARKDOWN
            )
            await loading_message.delete() # Clean up loading message

        except FileNotFoundError: # This shouldn't happen with file_id, but keep for safety
            print("Warning: bg_blackmarket.png not found (should be using file_id). Sending text message instead.")
            await loading_message.edit_text(full_caption, parse_mode=ParseMode.MARKDOWN) # Fallback to text
        except Exception as photo_err:
             print(f"Error sending blackmarket photo (ID: {BG_BLACKMARKET_FILE_ID}): {photo_err}. Sending text.")
             await loading_message.edit_text(full_caption, parse_mode=ParseMode.MARKDOWN) # Fallback to text

    except Exception as e:
        # Catch errors during data fetching or processing
        print(f"Error in /blackmarket command: {e}")
        if loading_message: # Try to edit the loading message
            try:
                await loading_message.edit_text("\u274c An error occurred while fetching market listings.") # Cross mark ❌
            except Exception as e_edit:
                 print(f"Failed to edit loading message on error: {e_edit}")
        else: # If loading message failed, send new error message
            await context.bot.send_message(chat_id=chat_id_to_use, text="\u274c An error occurred while fetching market listings.")




async def find_user_by_any_means(search_query: str):
    """
    Searches for a user by ID, Username, or Player Name.
    Returns: (user_ref, user_data) or (None, None)
    """
    search_query = search_query.strip()
    
    # Clean up input (remove @ if present)
    clean_query = search_query.lstrip("@")

    # ATTEMPT 1: Direct User ID (Best Match)
    # Check if the input is a valid Document ID
    doc_ref = db.collection("users").document(clean_query)
    doc = doc_ref.get()
    if doc.exists:
        return doc_ref, doc.to_dict()

    # ATTEMPT 2: Exact Username Match
    # (Matches @username)
    query = db.collection("users").where(filter=FieldFilter("username", "==", clean_query)).limit(1).stream()
    result = next(query, None)
    if result:
        return result.reference, result.to_dict()

    # ATTEMPT 3: Player Name / Display Name
    # (Matches "Sarath Das" or "Steel Fanged")
    query = db.collection("users").where(filter=FieldFilter("player_name", "==", search_query)).limit(1).stream()
    result = next(query, None)
    if result:
        return result.reference, result.to_dict()

    # ATTEMPT 4: NPC Name (Fallback for fake users)
    # Sometimes NPCs are saved with just 'name' or inside a different logic, 
    # but usually they follow the player_name convention above.
    
    return None, None


# --- (Add this new command function) ---

async def explain_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows an inline keyboard to choose a command for explanation."""
    
    # Sort keys for consistent order
    keys = sorted(COMMAND_EXPLANATIONS.keys())
    keyboard = []
    row = []

    # Loop through keys and build rows of 2 buttons
    for cmd_key in keys:
        # Clean up text: "guild_promote_officer" -> "Guild Promote Officer"
        button_text = cmd_key.replace("_", " ").title()
        
        # Add button to current row
        row.append(InlineKeyboardButton(button_text, callback_data=f"explain_command_{cmd_key}"))
        
        # If row has 2 buttons, add it to keyboard and reset
        if len(row) == 2:
            keyboard.append(row)
            row = []

    # If there is a leftover button, add it
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    text_msg = "📚 **SYSTEM KNOWLEDGE BASE**\n\nSelect a command protocol to analyze:"

    # Handle text vs button call
    if update.message:
        await update.message.reply_text(text_msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        # Send as a new message so the user can see the previous context if needed
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=text_msg,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

# (Replace your existing sell function with this)
@check_active_status
async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates the premium conversational flow to sell an item."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    if not user_doc.exists or "level" not in user_doc.to_dict():
        await update.message.reply_text("❌ You must activate your contract first.")
        return

    user_data = user_doc.to_dict()
    inventory_map = user_data.get("inventory", {})
    if not any(v > 0 for v in inventory_map.values()):
        await update.message.reply_text("❌ Your inventory is empty. You have nothing to list on the Black Market.")
        return

    # Set the state
    user_ref.update({"state": "awaiting_sell_info"})

    # --- Premium Visual Prompt ---
    prompt_text = (
        "**BLACK MARKET LISTING**\n\n"
        "Reply with the exact item name (use `/what` to copy) and the desired price (1-100).\n\n"
        "*Format:* `\"Item Name\" Price`\n"
        "*Example:* `\"Abyssal Amulet\" 50`"
    )

    try:
        # Send the background image with the instructions
        with open("bg_sell.png", "rb") as photo:
             await update.message.reply_photo(
                photo=photo,
                caption=prompt_text,
                parse_mode=ParseMode.MARKDOWN
            )
    except FileNotFoundError:
        # Fallback if the image is missing
        print("Warning: bg_sell.png not found. Sending text prompt only.")
        await update.message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"Error sending sell prompt photo: {e}")
        await update.message.reply_text("Error initiating sell command. Please try again.")




@check_active_status
async def use_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows a user to consume an item with robust name matching."""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/use <Item Name>`\nExample: `/use Scroll of Insight`", parse_mode=ParseMode.MARKDOWN)
        return

    # 1. Normalize User Input
    raw_input = " ".join(context.args).strip()
    clean_input = raw_input.lower().replace(" ", "_").replace("'", "").replace("’", "")
    
    # 2. Find Match in Configuration
    effect_data = None
    matched_key = None 

    for key, data in CONSUMABLE_EFFECTS.items():
        clean_key = key.lower().replace("'", "").replace("’", "")
        if clean_key == clean_input:
            effect_data = data
            matched_key = key
            break
    
    if not effect_data:
        await update.message.reply_text(f"❌ **{raw_input}** is not a usable item.")
        return

    official_name = effect_data["name"]

    # 3. Check Inventory
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    inventory = user_doc.to_dict().get("inventory", {})
    
    count = 0
    key_to_remove = None

    if inventory.get(official_name, 0) > 0:
        count = inventory.get(official_name)
        key_to_remove = official_name
    elif inventory.get(matched_key, 0) > 0:
        count = inventory.get(matched_key)
        key_to_remove = matched_key
    else:
        for inv_key, inv_count in inventory.items():
            clean_inv_key = inv_key.lower().replace(" ", "_").replace("'", "").replace("’", "")
            if clean_inv_key == clean_input and inv_count > 0:
                count = inv_count
                key_to_remove = inv_key
                break

    if count <= 0:
        await update.message.reply_text(f"❌ You do not have **{official_name}** in your inventory.")
        return

    # 4. Apply Effect Logic (Keep calculation in UTC for server consistency)
    duration = effect_data["duration_minutes"]
    expiry_time_utc = datetime.now(timezone.utc) + timedelta(minutes=duration)
    effect_type = effect_data["type"]
    effect_value = effect_data["value"]

    update_data = {
        f"inventory.{key_to_remove}": firestore.Increment(-1),
        f"active_effects.{effect_type}": {
            "value": effect_value,
            "expires_at": expiry_time_utc,
            "source": official_name
        }
    }

    user_ref.update(update_data)

    # 5. Success Message - CONVERT TO IST FOR DISPLAY
    # Add 5 hours and 30 minutes to UTC time
    expiry_time_ist = expiry_time_utc + timedelta(hours=5, minutes=30)
    # Format as "06:30 PM IST"
    expiry_str = expiry_time_ist.strftime("%I:%M %p IST")
    
    if effect_type == "xp_boost":
        emoji = "🧪"
        bonus_display = f"{int((effect_value - 1) * 100)}%" 
        desc = f"**XP Boost (+{bonus_display})**"
    elif effect_type == "loot_boost":
        emoji = "🍀"
        bonus_display = f"{int(effect_value * 100)}%"
        desc = f"**Loot Luck (+{bonus_display})**"
    else:
        emoji = "✨"
        desc = "**Special Effect**"

    await update.message.reply_text(
        f"{emoji} **ITEM CONSUMED** {emoji}\n\n"
        f"**{official_name}** used.\n"
        f"_{effect_data['desc']}_\n\n"
        f"⚡ **Active Effect:** {desc}\n"
        f"⏳ **Expires:** `{expiry_str}`",
        parse_mode=ParseMode.MARKDOWN
    )



# (Replace your existing 'buy' function with this)
@check_active_status
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates a premium purchase flow for a listed item."""
    user_id = str(update.effective_user.id) # Get user ID for potential future use

    if not context.args:
        await update.message.reply_text(
            "❌ Please specify the item you wish to acquire.\n"
            "*Usage:* `/buy <Full Item Name>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    item_name_input = " ".join(context.args).strip().strip('"')
    
    # --- Premium Loading Animation ---
    loading_message = await update.message.reply_text("⏳ *Accessing Black Market Network...*")
    await asyncio.sleep(0.7)

    # --- Find the Item ---
    market_ref = db.collection("market")
    # Search using the official name (case-insensitive search is harder, so rely on user inputting correctly)
    # A more robust search could involve querying lowercase names if the first fails.
    item_query = market_ref.where(filter=FieldFilter("item_name", "==", item_name_input)).where(filter=FieldFilter("is_sold", "==", False)).limit(1).stream()
    item_to_buy_doc = next(item_query, None)

    if not item_to_buy_doc:
        await loading_message.edit_text(f"❌ Item '{item_name_input}' not found or already sold on the Black Market. Use `/blackmarket` to see current listings.")
        return

    item_data = item_to_buy_doc.to_dict()
    price = item_data.get("price")
    seller_username = item_data.get("seller_username", "Unknown")
    
    # Fetch item rarity for display
    item_ref = db.collection("items").document(item_name_input.lower().replace(' ', '_'))
    item_info = item_ref.get().to_dict()
    item_rarity = item_info.get("rarity", "Item") if item_info else "Item"

    await loading_message.edit_text("🤝 *Initiating secure transaction protocol...*")
    await asyncio.sleep(1)

    # --- Construct Premium Caption ---
    admin_username = os.getenv("ADMIN_USERNAME", "EliteeconomiX") # Ensure this is set in your .env or config

    caption_text = (
        f"**PURCHASE PROTOCOL INITIATED**\n\n"
        f"**Item:** `{item_data.get('item_name')}` `[{item_rarity}]`\n"
        f"**Price:** `₹{price}`\n"
        f"**Seller:** @{seller_username}\n\n"
        f"--- **ACTION REQUIRED** ---\n"
        f"1. Contact Admin: @{admin_username}\n"
        f"   _(Direct Link: [t.me/{admin_username}])_\n" # Note: No slash before username here
        f"2. Send `₹{price}` via UPI/Bank.\n"
        f"3. Provide payment proof (screenshot).\n\n"
        f"The Admin will verify and transfer the item to your inventory upon confirmation."
    )

    # --- Send Themed Image with Caption ---
    try:
        with open("bg_buy.png", "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=caption_text,
                parse_mode=ParseMode.MARKDOWN
            )
        await loading_message.delete() # Clean up loading message

    except FileNotFoundError:
        print("Warning: bg_buy.png not found. Sending text message instead.")
        await loading_message.edit_text(caption_text, parse_mode=ParseMode.MARKDOWN) # Fallback to text
    except Exception as e:
        print(f"Error sending buy prompt photo: {e}")
        await loading_message.edit_text("Error initiating purchase. Please try again.")



@admin_only
async def set_next_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Monarch only: Queues a specific mission for a player's NEXT /mission request."""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/set_next_mission @username mission_id`")
        return

    target_username = context.args[0]
    mission_id = " ".join(context.args[1:]).strip().lower().replace(" ", "_")

    # 1. Find the User
    user_doc = await find_user_by_username(target_username)
    if not user_doc:
        await update.message.reply_text("❌ Hunter not found.")
        return

    # 2. Find the Mission
    found_mission = None
    for diff in DIFFICULTIES:
        for mtype in TYPES:
            m_ref = db.collection("missions").document("MonarchSystem").collection(diff).document(mtype).collection("list").document(mission_id).get()
            if m_ref.exists:
                found_mission = m_ref.to_dict()
                found_mission["difficulty"] = diff
                found_mission["type"] = mtype
                break
        if found_mission: break

    if not found_mission:
        await update.message.reply_text(f"❌ Mission `{mission_id}` not found.")
        return

    # 3. Store it in a 'queued_mission' field
    db.collection("users").document(user_doc.id).update({"queued_mission": found_mission})
    await update.message.reply_text(f"✅ Target Locked. @{target_username} will receive '{found_mission['title']}' on their next request.")


# (Replace your entire 'what' function with this)

# (Replace your entire 'what' function with this)

# --- (Replace your old /what command with this corrected version) ---
@check_active_status
async def what(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides a premium list of the user's assets with usage and selling instructions."""
    user_id = str(update.effective_user.id)
    loading_message = await update.message.reply_text("📦 Accessing your inventory...")

    try:
        user_doc = db.collection("users").document(user_id).get()
        
        if not user_doc.exists or "level" not in user_doc.to_dict():
            await loading_message.edit_text("⚠️ You must activate your contract first.")
            return

        inventory_map = user_doc.to_dict().get("inventory", {})
        potential_sellable = {item: count for item, count in inventory_map.items() if count > 0}
        
        if not potential_sellable:
            await loading_message.edit_text("🎒 Your inventory is empty. You have no items to sell.")
            return
            
        # Optimization: Fetch all items once
        all_items_docs = db.collection("items").stream()
        item_db_lookup = {doc.id: doc.to_dict() for doc in all_items_docs}

        # Build List
        assets_text = ""
        rarity_colors = {"Common": "⚪️", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
        valid_count = 0
        
        for item_key, count in potential_sellable.items():
            doc_id = item_key.lower().replace(' ', '_').replace("'", "'")
            item_info = item_db_lookup.get(doc_id)
            
            if item_info:
                valid_count += 1
                rarity = item_info.get("rarity", "Common")
                official_name = item_info.get("name", item_key)
                emoji = rarity_colors.get(rarity, "⚫️")
                
                # Check usable status
                tag = ""
                if doc_id in CONSUMABLE_EFFECTS:
                    tag = " `[⚡USE]`"
                
                assets_text += f"{emoji} `{official_name}` `(x{count})`{tag}\n"

        if valid_count == 0:
            await loading_message.edit_text("🎒 Your inventory contains only invalid items.")
            return

        full_text_message = (
            f"**YOUR ASSETS**\n"
            f"_(Tap an item name below to copy it)_\n\n"
            f"{assets_text}\n"
            f"--- **INSTRUCTIONS** ---\n"
            f"⚡ **To Use Consumables:**\n"
            f"`/use \"Item Name\"`\n\n"
            f"💰 **To Sell on Black Market:**\n"
            f"`/sell \"Item Name\" <Price>`"
        )
        
        # --- FIX: Use File ID for Instant Send ---
        try:
            # We use the constant BG_WHAT_FILE_ID instead of open()
            # This makes the image appear instantly without uploading.
            await update.message.reply_photo(
                photo=BG_WHAT_FILE_ID, 
                caption="**YOUR ASSETS**", 
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            # If the ID fails, we just skip the image (no error for user)
            pass

        await update.message.reply_text(full_text_message, parse_mode=ParseMode.MARKDOWN)
        await loading_message.delete()
        
    except Exception as e:
        await loading_message.edit_text("❌ An error occurred.")
        print(f"Error in /what command: {e}")


# --- SHADOW REGIMENT ---

async def extract_shadow(update, user_ref, mission_data):
    """Creates a new shadow soldier after a mission."""
    message = update.message or update.callback_query.message
    
    prefixes = ["Shadow", "Void", "Abyssal", "Dusk"]
    suffixes = {
        "Physical": ["Brute", "Knight", "Vanguard"], "Mental": ["Sage", "Strategist", "Oracle"],
        "Spiritual": ["Acolyte", "Wraith", "Phantom"], "All-Round": ["Guardian", "Legionnaire", "Centurion"]
    }
    mission_type = mission_data.get("type", "All-Round")
    shadow_name = f"{random.choice(prefixes)} {random.choice(suffixes[mission_type])}"

    bonus = {"type": f"xp_boost_{mission_type.lower()}", "value": 0.01} # +1% XP boost
    shadow_data = {
        "name": shadow_name, "source_mission": mission_data.get("title", "Unknown"),
        "bonus": bonus, "rank": "Standard", "extracted_at": firestore.SERVER_TIMESTAMP
    }
    user_ref.collection("shadows").add(shadow_data)

    await asyncio.sleep(1)
    extraction_text = (
        f"**A new shadow pledges its loyalty!**\n\n"
        f"From the echoes of your completed trial, the **{shadow_name}** has arisen.\n"
        f"It now serves you, granting a permanent bonus to your future endeavors."
    )
    voice_path = "arise.ogg"
    if os.path.exists(voice_path):
        await message.reply_voice(voice=open(voice_path, "rb"))
    await message.reply_text(extraction_text, parse_mode=ParseMode.MARKDOWN)


@check_active_status
async def regiment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's collected shadow soldiers."""
    user_id = str(update.effective_user.id)
    all_shadows = [doc.to_dict() for doc in db.collection("users").document(user_id).collection("shadows").stream()]

    if not all_shadows:
        await update.message.reply_text("Your shadow army is empty. Complete difficult missions to extract new soldiers. Arise.")
        return

    message_text = f"**Your Shadow Regiment ({len(all_shadows)} Soldiers)**\n\n"
    for shadow in all_shadows:
        bonus = shadow.get("bonus", {})
        bonus_type = bonus.get("type", "unknown_bonus").replace("xp_boost_", "").capitalize()
        boost_percent = int(bonus.get("value", 0) * 100)
        bonus_desc = f"+{boost_percent}% XP from {bonus_type} Missions"
        message_text += f"- `[{shadow.get('rank')}]` **{shadow.get('name')}**\n  `┗ Grants: {bonus_desc}`\n\n"

    message_text += "*The shadows silently await your command...*"
    await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)


# --- GUILD SYSTEM ---

# --- (Replace your old /guild command) ---
@check_active_status
async def guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main hub for guild commands, now shows the dynamic guild card."""
    user_id = str(update.effective_user.id)
    user_doc = db.collection("users").document(user_id).get()

    if not user_doc.exists or "rank" not in user_doc.to_dict():
        await update.message.reply_text("You must be an active Hunter to interact with Guilds.")
        return
    
    guild_id = user_doc.to_dict().get("guild_id")
    
    if guild_id:
        loading_msg = await update.message.reply_text("🛡️ Accessing Guild Archives... Generating banner...")
        guild_ref = db.collection("guilds").document(guild_id)
        guild_doc = guild_ref.get()
        
        if guild_doc.exists:
            guild_data = guild_doc.to_dict()
            card_path = None
            try:
                # Generate the new dynamic card
                card_path = generate_guild_card(guild_data)
                
                caption = (
                    f"**[{guild_data.get('tag')}] {guild_data.get('name')}**\n\n"
                    "Use the Guild Hall for all actions:\n"
                    "► `/guild_hall`"
                )
                
                with open(card_path, "rb") as photo:
                    await update.message.reply_photo(
                        photo=photo, 
                        caption=caption, 
                        parse_mode=ParseMode.MARKDOWN
                    )
                await loading_msg.delete()

            except Exception as e:
                print(f"Error generating/sending guild card: {e}")
                await loading_msg.edit_text("Error: Could not generate Guild Banner.")
            finally:
                if card_path and os.path.exists(card_path):
                    os.remove(card_path)
        else:
            # Data mismatch, clean up user's broken guild ID
            await update.message.reply_text("Error: Could not find your guild's data. It may have been disbanded. Cleaning your profile...")
            db.collection("users").document(user_id).update({
                "guild_id": firestore.DELETE_FIELD,
                "guild_role": firestore.DELETE_FIELD
            })
    else:
        # User is not in a guild
        help_text = ("⚔️ **Shadow Guilds** ⚔️\n\nYou are not currently in a Guild.\n\n"
                     "`/guild_create` - Form a new guild.\n"
                     "To join, you must receive an invitation from a Guild Leader.")
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)




@leader_only
async def guild_promote_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Leader Only) Promotes a Member to Officer."""
    leader_id = str(update.effective_user.id)
    leader_doc = db.collection("users").document(leader_id).get()
    guild_id = leader_doc.to_dict().get("guild_id")

    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/guild_promote_officer @username`", parse_mode=ParseMode.MARKDOWN)
        return

    target_username = context.args[0].replace("@", "").strip().lower()
    
    # Find Target User
    users_query = db.collection("users").where(filter=FieldFilter("username", "==", target_username)).limit(1).stream()
    target_doc = next(users_query, None)

    if not target_doc:
        await update.message.reply_text("❌ User not found.")
        return

    target_data = target_doc.to_dict()
    if target_data.get("guild_id") != guild_id:
        await update.message.reply_text("❌ That user is not in your guild.")
        return

    if target_data.get("guild_role") == "Officer":
        await update.message.reply_text("❌ They are already an Officer.")
        return

    # Update DB
    batch = db.batch()
    # 1. Update Guild Member List
    guild_ref = db.collection("guilds").document(guild_id)
    batch.update(guild_ref, {f'members.{target_doc.id}': "Officer"})
    # 2. Update User Profile
    batch.update(target_doc.reference, {"guild_role": "Officer"})
    batch.commit()

    await update.message.reply_text(f"🎖️ **Promotion!** @{target_username} is now a Guild Officer.", parse_mode=ParseMode.MARKDOWN)


@leader_only
async def guild_demote_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Leader Only) Demotes an Officer back to Member."""
    leader_id = str(update.effective_user.id)
    leader_doc = db.collection("users").document(leader_id).get()
    guild_id = leader_doc.to_dict().get("guild_id")

    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/guild_demote_officer @username`", parse_mode=ParseMode.MARKDOWN)
        return

    target_username = context.args[0].replace("@", "").strip().lower()
    
    # Find Target
    users_query = db.collection("users").where(filter=FieldFilter("username", "==", target_username)).limit(1).stream()
    target_doc = next(users_query, None)

    if not target_doc: 
        await update.message.reply_text("❌ User not found.")
        return

    if target_doc.to_dict().get("guild_role") != "Officer":
        await update.message.reply_text("❌ That user is not an Officer.")
        return

    # Update DB
    batch = db.batch()
    guild_ref = db.collection("guilds").document(guild_id)
    batch.update(guild_ref, {f'members.{target_doc.id}': "Member"})
    batch.update(target_doc.reference, {"guild_role": "Member"})
    batch.commit()

    await update.message.reply_text(f"📉 @{target_username} has been demoted to Member.")








# --- (Add this placeholder function in your GUILD SYSTEM section) ---

# --- (REPLACE your old guild_mission function with this) ---

@check_active_status
async def guild_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the status of the current guild mission."""
    user_id = str(update.effective_user.id)
    user_doc = db.collection("users").document(user_id).get()
    user_data = user_doc.to_dict()

    message = update.message or update.callback_query.message

    if not user_data or not user_data.get("guild_id"):
        await message.reply_text("🛡️ You must be in a guild to view guild contracts.")
        return

    guild_ref = db.collection("guilds").document(user_data["guild_id"])
    guild_doc = guild_ref.get()
    if not guild_doc.exists:
        await message.reply_text("❌ Your guild data could not be found.")
        return
        
    guild_data = guild_doc.to_dict()
    active_mission = guild_data.get("active_mission")
    
    if active_mission:
        # --- A mission is active, display its status ---
        title = active_mission.get("title", "Unknown Contract")
        desc = active_mission.get("description", "No details available.")
        
        current = active_mission.get("current_progress", 0)
        target = active_mission.get("goal", 0) # Use 'goal' field
        
        # Create a simple progress bar
        progress_percent = (current / target) if target > 0 else 0
        bar_length = 20 # 20 chars long
        filled_length = int(bar_length * progress_percent)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        status_text = (
            f"**ACTIVE GUILD CONTRACT** 📜\n\n"
            f"**Title:** {title}\n"
            f"**Objective:** _{desc}_\n\n"
            f"**Progress:**\n"
            f"`{bar}`\n"
            f"`{current:,} / {target:,}`"
        )
        await message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        
    else:
        # --- No mission is active ---
        if user_data.get("guild_role") == "Leader":
            await message.reply_text(
                "There is no active Guild Contract.\n\n"
                "As Guild Leader, you can start one with:\n"
                "► `/guild_mission_start`"
            , parse_mode=ParseMode.MARKDOWN)
        else:
            await message.reply_text("There is no active Guild Contract. Await orders from your Leader.")


# --- (ADD this new function right after guild_mission) ---

@leader_only
@check_active_status
async def guild_mission_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Leader Only) Starts a new random guild mission from the weekly_pool."""
    user_id = str(update.effective_user.id)
    user_data = db.collection("users").document(user_id).get().to_dict()
    
    guild_ref = db.collection("guilds").document(user_data["guild_id"])
    guild_doc = guild_ref.get()
    if not guild_doc.exists:
        await update.message.reply_text("❌ Your guild data could not be found.")
        return
        
    guild_data = guild_doc.to_dict()
    
    if guild_data.get("active_mission"):
        await update.message.reply_text("❌ A Guild Contract is already in progress. Complete it first.")
        return
        
    loading_msg = await update.message.reply_text("Searching for a new Guild Contract...")
    
    # --- [NEW] Fetch from your exact DB path ---
    try:
        missions_ref = db.collection("guild_missions").document("weekly_pool").collection("missions")
        all_missions = [doc for doc in missions_ref.stream()]
        
        if not all_missions:
            await loading_msg.edit_text("❌ No Guild Contracts found in the database. Contact Admin.")
            return
            
        mission_doc = random.choice(all_missions)
        mission_data = mission_doc.to_dict()
        
        # Set initial progress
        mission_data["current_progress"] = 0
        
        # Set it as the active mission on the guild
        guild_ref.update({"active_mission": mission_data})
        
        await loading_msg.edit_text("✅ Contract acquired!")
        
        # --- Broadcast to Guild ---
        broadcast_message = (
            f"**NEW GUILD CONTRACT ISSUED!**\n\n"
            f"Your Leader has activated a new contract:\n"
            f"**Title:** {mission_data.get('title')}\n"
            f"**Objective:** _{mission_data.get('description')}_\n\n"
            f"All personal missions completed by guild members will now contribute to this goal.\n"
            f"Check progress with `/guild_mission`."
        )
        
        asyncio.create_task(broadcast_to_guild(
            context,
            guild_data.get("members", {}).keys(),
            broadcast_message
        ))
        
    except Exception as e:
        print(f"Error fetching/starting guild mission: {e}")
        await loading_msg.edit_text(f"❌ An error occurred: {e}")




# --- (Add these 3 new commands to your GUILD SYSTEM section) ---

# --- (Replace your broken guild_hall function with this one) ---

# --- (Replace your broken guild_hall function with this one) ---
@check_active_status
async def guild_hall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the premium Guild Hall, the central hub for guild actions."""
    user_id = str(update.effective_user.id)
    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists or not user_doc.to_dict().get("guild_id"):
        await update.message.reply_text("❌ You must be in a guild to access its hall.")
        return

    guild_id = user_doc.to_dict().get("guild_id")
    guild_doc = db.collection("guilds").document(guild_id).get()
    if not guild_doc.exists:
        await update.message.reply_text("❌ Your guild data could not be found.")
        return
        
    guild_data = guild_doc.to_dict()
    guild_name = guild_data.get("name", "Your Guild")

    # --- Construct the hub caption ---
    caption = (
        f"**Welcome to the [{guild_data.get('tag')}] {guild_name} Hall**\n"
        # --- THIS IS THE FIX ---
        # Changed the line from an f-string (f"...") to a regular string ("...")
        # to prevent the f-string parser from conflicting with the _ italics.
        "_{The air is thick with ambition. Your banner hangs high._}\n\n"
        # --- END OF FIX ---
        f"**WAR COUNCIL**\n"
        f"► `/guild_mission` - View the active Guild Contract\n\n"
        f"**VAULT & ROSTER**\n"
        f"► `/guild_treasury` - Access the Guild Vault\n"
        f"► `/guild_donate` - Donate items to the Vault\n"
        f"► `/guild_members` - View the Hunter Roster\n\n"
        f"**LEADERSHIP** (Leader/Officer)\n"
        f"► `/guild_invite` - Invite a new Hunter\n"
        f"► `/guild_kick` - Remove a member\n"
        f"**LEADERSHIP**\n"
        f"► `/guild_invite` - Invite Hunter (Officer+)\n"
        f"► `/guild_kick` - Remove Member (Officer+)\n"
        f"► `/guild_promote_officer` - (Leader Only)\n"
    )

    try:
        await update.message.reply_photo(
            photo=BG_GUILD_HALL_FILE_ID,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Error sending guild hall photo: {e}. Using text fallback.")
        await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)




@admin_only
async def create_rival_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Creates a System-Controlled Guild with a generated NPC Leader.
    Usage: /create_rival_guild "Guild Name" "TAG" Level
    Example: /create_rival_guild "The Iron Hands" "IRON" 5
    """
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: `/create_rival_guild \"Name\" \"TAG\" Level`")
        return

    # 1. Parse Arguments (names might have spaces)
    try:
        # crude parsing for quotes
        args_str = " ".join(context.args)
        import shlex
        parsed_args = shlex.split(args_str)
        
        name = parsed_args[0]
        tag = parsed_args[1].upper()
        level = int(parsed_args[2])
    except:
        await update.message.reply_text("❌ Error parsing. Use quotes for names.")
        return

    # 2. Check for Duplicate Tag
    existing = db.collection("guilds").where(filter=FieldFilter("tag", "==", tag)).get()
    if list(existing):
        await update.message.reply_text(f"❌ Guild Tag '{tag}' already exists.")
        return

    # 3. Generate NPC Leader
    leader_id = f"npc_leader_{str(uuid.uuid4())[:8]}"
    leader_name = f"Grandmaster_{tag}"
    
    # Create the Leader Doc (So the guild doesn't crash if clicked)
    db.collection("users").document(leader_id).set({
        "username": leader_name.lower(),
        "player_name": leader_name,
        "is_npc": True,
        "guild_id": f"guild_{tag}",
        "guild_role": "Leader",
        "level": level + 10, # Leader is stronger than guild
        "xp": 50000
    })

    # 4. Create the Guild
    guild_id = f"guild_{tag}"
    
    # Calculate fake stats based on requested level
    base_xp = level * 10000 
    
    guild_data = {
        "name": name,
        "tag": tag,
        "description": "A powerful rival organization controlled by the System.",
        "leader_id": leader_id,
        "created_at": firestore.SERVER_TIMESTAMP,
        "level": level,
        "xp": base_xp,
        "members": [leader_id], # Real list with NPC ID
        "member_count": random.randint(5, 50), # Fake visual count
        "capacity": 50,
        "is_system_guild": True, # Flag to identify it
        "active_mission": None
    }
    
    db.collection("guilds").document(guild_id).set(guild_data)
    
    await update.message.reply_text(
        f"🏰 **Rival Guild Established**\n"
        f"**Name:** {name} [{tag}]\n"
        f"**Level:** {level}\n"
        f"**Leader:** {leader_name} (NPC)\n"
        f"**Fake Members:** {guild_data['member_count']}\n\n"
        f"Use `/control_guild` to modify its stats."
    )




@admin_only
async def control_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Modifies any Guild's stats (Real or Rival).
    Usage: /control_guild <TAG> <xp|level|members> <value>
    Example: /control_guild IRON xp 50000
    """
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: `/control_guild <TAG> <xp/level/members> <value>`")
        return

    tag = context.args[0].upper()
    field = context.args[1].lower()
    value = int(context.args[2])

    # Find Guild ID by Tag
    q = db.collection("guilds").where(filter=FieldFilter("tag", "==", tag)).limit(1).stream()
    guild_doc = next(q, None)
    
    if not guild_doc:
        await update.message.reply_text("❌ Guild not found.")
        return

    guild_ref = db.collection("guilds").document(guild_doc.id)

    # Update logic
    if field == "xp":
        guild_ref.update({"xp": value})
        await update.message.reply_text(f"✅ Set **{tag}** XP to `{value}`.")
        
    elif field == "level":
        guild_ref.update({"level": value})
        await update.message.reply_text(f"✅ Set **{tag}** Level to `{value}`.")
        
    elif field == "members":
        # Only works visually for System Guilds
        guild_ref.update({"member_count": value})
        await update.message.reply_text(f"✅ Set **{tag}** Member Count to `{value}`.")
        
    else:
        await update.message.reply_text("❌ Unknown field. Use: `xp`, `level`, `members`")


# --- (Replace your old /guild_treasury command) ---

async def guild_treasury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the items stored in the guild's treasury."""
    user_id = str(update.effective_user.id)
    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists or not user_doc.to_dict().get("guild_id"):
        await update.message.reply_text("❌ You must be in a guild to view its treasury.")
        return

    loading_msg = await update.message.reply_text("Accessing Vault... Cross-referencing item database...")

    try:
        # --- FIX: Fetch all item data ONCE to avoid blocking in a loop ---
        all_items_docs = db.collection("items").stream()
        item_db_lookup = {}
        for doc in all_items_docs:
            item_data = doc.to_dict()
            item_db_lookup[doc.id] = {
                "rarity": item_data.get("rarity", "Common"),
                "name": item_data.get("name", doc.id)
            }
        # --- End of Fix ---

        guild_id = user_doc.to_dict().get("guild_id")
        guild_doc = db.collection("guilds").document(guild_id).get()
        if not guild_doc.exists:
            await loading_msg.edit_text("❌ Your guild data could not be found.")
            return
            
        guild_data = guild_doc.to_dict()
        treasury = guild_data.get("treasury", {})
        
        if not treasury:
            await loading_msg.edit_text("Vault access granted. The Guild Treasury is currently empty.")
            return

        message_text = f"**[{guild_data.get('tag')}] {guild_data.get('name')} - Treasury**\n\n"
        
        rarity_colors = {"Common": "⚪️", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}
        
        for item_name_in_treasury, count in treasury.items():
            if count <= 0: continue
            
            # --- FIX: Use our local lookup (fast) ---
            item_doc_id = item_name_in_treasury.lower().replace(' ', '_')
            item_info = item_db_lookup.get(item_doc_id)
            
            rarity = "Common"
            official_name = item_name_in_treasury # Fallback
            
            if item_info:
                rarity = item_info["rarity"]
                official_name = item_info["name"] # Use the official cased name
            # --- End of Fix ---
                
            rarity_emoji = rarity_colors.get(rarity, "⚫️")
            message_text += f"{rarity_emoji} `{official_name}` `(Qty: {count})`\n"
            
        message_text += "\n_Items stored here can be used for Guild events or distributed by the Leader._"
        await loading_msg.edit_text(message_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        print(f"Error in /guild_treasury: {e}")
        await loading_msg.edit_text(f"❌ An error occurred while fetching the treasury: {e}")



@check_active_status
async def leaderboard_guilds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the server-wide Guild Leaderboard."""
    message = update.message or update.callback_query.message
    loading_msg = await message.reply_text("🛡️ Compiling Guild Rankings...")

    try:
        # 1. Fetch All Guilds
        # Note: For massive scale, you'd use a Firestore Index/Query. 
        # For now, sorting in Python is stable and doesn't require console setup.
        all_guilds = [doc.to_dict() for doc in db.collection("guilds").stream()]
        
        if not all_guilds:
            await loading_msg.edit_text("❌ No guilds have been formed yet.")
            return

        # 2. Sort Logic (Primary: Level Descending, Secondary: XP Descending)
        sorted_guilds = sorted(all_guilds, key=lambda g: (-g.get('level', 1), -g.get('xp', 0)))

        # 3. Generate Banner for the #1 Guild
        top_guild = sorted_guilds[0]
        banner_path = None
        try:
            # We reuse your existing function!
            banner_path = generate_guild_card(top_guild)
        except Exception as e:
            print(f"Error generating top guild banner: {e}")

        # 4. Build Text List
        lb_text = "🏆 **GUILD POWER RANKINGS** 🏆\n\n"
        
        for i, guild in enumerate(sorted_guilds[:10], 1):
            name = guild.get("name", "Unknown")
            tag = guild.get("tag", "???")
            lvl = guild.get("level", 1)
            xp = guild.get("xp", 0)
            members = guild.get("member_count", 0)
            
            # Medal Icons for Top 3
            icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**#{i}**"
            
            lb_text += f"{icon} **[{tag}] {name}**\n"
            lb_text += f"   ╚ Lv.{lvl} • {xp:,} XP • {members} Members\n"

        lb_text += "\n_Rankings are based on Guild Level and Total GXP._"

        # 5. Send Message
        await loading_msg.delete()
        
        if banner_path:
            with open(banner_path, "rb") as photo:
                await message.reply_photo(
                    photo=photo,
                    caption=lb_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            # Cleanup
            if os.path.exists(banner_path):
                os.remove(banner_path)
        else:
            # Fallback if image fails
            await message.reply_text(lb_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await loading_msg.edit_text(f"❌ Error fetching leaderboard: {e}")
        print(f"Guild LB Error: {e}")



@admin_only
async def add_fake_damage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adds a fake entry to the World Boss leaderboard.
    Usage: /fake_damage <Name> <Damage>
    Example: /fake_damage James 2000
    """
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/fake_damage <Name> <Amount>`")
        return

    # 1. Parse Arguments
    try:
        # If name is "Dark Knight", handles spaces
        damage_amount = int(context.args[-1])
        fake_name = " ".join(context.args[:-1])
    except ValueError:
        await update.message.reply_text("❌ Damage must be a number (e.g. 500).")
        return

    # 2. Generate a Fake ID (e.g., npc_james)
    fake_id = f"npc_{fake_name.lower().replace(' ', '_')}"

    # 3. Create/Update the Dummy User in DB
    # (We need this so the Leaderboard code finds a name when it looks up the ID)
    user_ref = db.collection("users").document(fake_id)
    if not user_ref.get().exists:
        user_ref.set({
            "username": fake_name,      # Leaderboard looks for this
            "player_name": fake_name,   # Or this
            "is_npc": True,             # Mark as fake
            "level": random.randint(5, 50), # Random level for realism
            "guild_id": "guild_npc"     # Optional: Put them in a fake guild
        })

    # 4. Find Active Boss
    boss_query = db.collection("world_bosses").where(filter=FieldFilter("is_active", "==", True)).limit(1).stream()
    active_boss_doc = next(boss_query, None)

    if not active_boss_doc:
        await update.message.reply_text("❌ No Active Boss found.")
        return

    boss_ref = active_boss_doc.reference

    # 5. Apply Damage (Transaction safe)
    @firestore.transactional
    def _apply_fake_damage(transaction, ref, uid, dmg):
        snapshot = ref.get(transaction=transaction)
        curr_hp = snapshot.get("current_health")
        
        # Calculate new HP
        new_hp = curr_hp - dmg
        if new_hp < 0: new_hp = 0

        # Update
        transaction.update(ref, {
            "current_health": new_hp,
            f"damage_log.{uid}": firestore.Increment(dmg)
        })
        return new_hp

    transaction = db.transaction()
    new_hp = _apply_fake_damage(transaction, boss_ref, fake_id, damage_amount)

    # 6. Success Message
    await update.message.reply_text(
        f"👻 **Phantom Strike Recorded**\n"
        f"User: `{fake_name}` (NPC)\n"
        f"Damage: `{damage_amount:,}`\n"
        f"Boss HP: `{new_hp:,}`"
    )



@admin_only
async def force_reset_guild_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Wipes the active mission for a target guild to fix bugs."""
    if not context.args:
        await update.message.reply_text("Usage: `/force_reset_guild_mission @LeaderUsername`")
        return

    username = context.args[0]
    user_doc = await find_user_by_username(username)
    
    if not user_doc:
        await update.message.reply_text("User not found.")
        return

    guild_id = user_doc.to_dict().get("guild_id")
    if not guild_id:
        await update.message.reply_text("User is not in a guild.")
        return

    # WIPE THE MISSION
    db.collection("guilds").document(guild_id).update({
        "active_mission": firestore.DELETE_FIELD
    })
    
    await update.message.reply_text("✅ Guild Mission Wiped. You can now run `/guild_mission_start` to get a fresh (fixed) contract.")




async def guild_donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates the conversational flow to donate an item to the guild."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    if not user_doc.exists or "level" not in user_doc.to_dict():
        await update.message.reply_text("❌ You must be an active Hunter to donate.")
        return
        
    user_data = user_doc.to_dict()
    if not user_data.get("guild_id"):
        await update.message.reply_text("❌ You must be in a guild to donate.")
        return

    inventory_map = user_data.get("inventory", {})
    if not any(v > 0 for v in inventory_map.values()):
        await update.message.reply_text("❌ Your inventory is empty. You have nothing to donate.")
        return

    # Set the new state
    user_ref.update({"state": "awaiting_donation_info"})

    prompt_text = (
        "**GUILD DONATION**\n\n"
        "Reply with the exact item name (use `/what` to copy) and the amount to donate.\n\n"
        "*Format:* `\"Item Name\" Amount`\n"
        "*Example:* `\"Shadow Key\" 10`"
    )
    
    # We can reuse the /sell background image if we want
    try:
        await update.message.reply_photo(
            photo=BG_SELL_FILE_ID, 
            caption=prompt_text,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Warning: BG_SELL_FILE_ID not found. Sending text fallback for donate. {e}")
        await update.message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN)





async def guild_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversational process for creating a guild."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    if not user_doc.exists: return
    user_data = user_doc.to_dict()

    if user_data.get("guild_id"):
        await update.message.reply_text("❌ You are already in a Guild. Leave with `/guild_leave` first.")
        return
    
    ## FIX APPLIED: Correct rank check logic ##
    user_rank_value = get_rank_sort_value(user_data.get("rank", "E"))
    min_rank_value_to_create = get_rank_sort_value(MIN_RANK_TO_CREATE_GUILD)
    if user_rank_value > min_rank_value_to_create:
        await update.message.reply_text(f"❌ You must be at least **{MIN_RANK_TO_CREATE_GUILD}-Rank** to form a Guild.", parse_mode=ParseMode.MARKDOWN)
        return

    user_ref.update({"state": "awaiting_guild_name"})
    await update.message.reply_text("⚜️ **New Guild Formation** ⚜️\nEnter the desired full name for your new Guild (e.g., IronBlood).")


async def guild_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows a Guild Leader to rename their guild."""
    user_id = str(update.effective_user.id)
    user_doc = db.collection("users").document(user_id).get()

    ## FIX APPLIED: Standardized on guild_role ##
    if not user_doc.exists or user_doc.to_dict().get("guild_role") != "Leader":
        await update.message.reply_text("❌ Only the Guild Leader can rename the guild.")
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: `/guild_rename <The New Name>`", parse_mode=ParseMode.MARKDOWN)
        return

    new_name = " ".join(context.args)
    if not (3 <= len(new_name) <= 25):
        await update.message.reply_text("❌ Guild name must be 3-25 characters.")
        return
    
    # Check for name uniqueness
    name_check = db.collection("guilds").where(filter=FieldFilter("name_lower", "==", new_name.lower())).limit(1).get()
    if len(list(name_check)) > 0:
        await update.message.reply_text(f"❌ A Guild with the name '{new_name}' already exists.")
        return

    guild_id = user_doc.to_dict()["guild_id"]
    guild_ref = db.collection("guilds").document(guild_id)
    guild_ref.update({"name": new_name, "name_lower": new_name.lower()})
    
    await update.message.reply_text(f"✅ Your Guild has been renamed to **{new_name}**.", parse_mode=ParseMode.MARKDOWN)



@leadership_only  # <--- CHANGED from @leader_only
async def guild_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Invites a user (Leader & Officers can use this)."""
    caller_id = str(update.effective_user.id)
    caller_data = db.collection("users").document(caller_id).get().to_dict()
    guild_id = caller_data["guild_id"]
    
    guild_ref = db.collection("guilds").document(guild_id)
    guild_doc = guild_ref.get()
    if not guild_doc.exists: return

    guild_data = guild_doc.to_dict()
    if guild_data.get("member_count", 0) >= MAX_GUILD_MEMBERS:
        await update.message.reply_text(f"❌ Your Guild is full (Max: {MAX_GUILD_MEMBERS}).")
        return

    if not context.args:
        await update.message.reply_text("❌ *Usage:* `/guild_invite @username`", parse_mode=ParseMode.MARKDOWN)
        return
        
    invited_username = context.args[0].replace("@", "").strip().lower()
    users_query = db.collection("users").where(filter=FieldFilter("username", "==", invited_username)).limit(1).stream()
    invited_user_doc = next(users_query, None)
    
    if not invited_user_doc:
        await update.message.reply_text(f"❌ Could not find a Hunter with the username @{invited_username}.")
        return
    
    if invited_user_doc.to_dict().get("guild_id"):
        await update.message.reply_text("❌ That Hunter is already in another guild.")
        return
    
    invited_user_doc.reference.update({f'guild_invites.{guild_id}': guild_data["name"]})
    await update.message.reply_text(f"✅ An invitation to join **{guild_data['name']}** has been sent to @{invited_username}.", parse_mode=ParseMode.MARKDOWN)

    try:
        invite_text = f"⚔️ You have been invited to join the **{guild_data['name']}** Guild by @{caller_data['username']}!"
        keyboard = [[InlineKeyboardButton("✅ Accept Invite", callback_data=f"guild_accept_{guild_id}")]]
        await context.bot.send_message(
            chat_id=invited_user_doc.id, text=invite_text,
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Error sending invite DM: {e}")





# List of "Cool" names for your NPCs
NPC_NAMES = ["Kael", "Viper", "Ghost", "SysAdmin", "Neo", "Jin", "Alucard", "Unknown", "Cipher", "Raven"]

@admin_only
async def create_npc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a Fake User (NPC) in the database."""
    
    # 1. Generate Fake Identity
    fake_id = f"npc_{str(uuid.uuid4())[:8]}" # e.g., npc_a1b2c3d4
    name = random.choice(NPC_NAMES) + f"_{random.randint(10, 99)}"
    
    # 2. Determine Stats (Randomized for realism)
    level = random.randint(5, 50)
    # Calculate XP based on level so math works
    xp = get_level_start_xp(level) + random.randint(0, 500)
    
    rank_map = {1: "E", 10: "D", 25: "C", 45: "B", 70: "A", 100: "S"}
    # Find rank based on level
    rank = "E"
    for lvl_req, r_name in rank_map.items():
        if level >= lvl_req:
            rank = r_name

    # 3. Create Document
    npc_data = {
        "username": name.lower(),
        "player_name": name,
        "username_initial": name, # No @ symbol for NPCs usually
        "telegram_id": fake_id, # Fake ID
        "level": level,
        "xp": xp,
        "rank": rank,
        "is_npc": True, # <--- IMPORTANT FLAG
        "inventory": {
            "Scroll of Insight": random.randint(1, 5),
            "Health Potion": random.randint(1, 10)
        },
        "joined_at": firestore.SERVER_TIMESTAMP
    }
    
    db.collection("users").document(fake_id).set(npc_data)
    
    await update.message.reply_text(
        f"👤 **Shadow Hunter Created**\n"
        f"Name: `{name}`\n"
        f"ID: `{fake_id}`\n"
        f"Level: {level} ({rank}-Rank)"
    )


@admin_only
async def npc_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forces an NPC to perform a specific game action."""
    try:
        if len(context.args) < 2:
            raise ValueError
        
        # Determine Target (Accepts Username or ID)
        target_input = context.args[0]
        action = context.args[1].lower()
        
        # Search for NPC
        target_doc = None
        if target_input.startswith("npc_"):
            target_doc = db.collection("users").document(target_input).get()
        else:
            # Search by name if ID not provided
            q = db.collection("users").where(filter=FieldFilter("username", "==", target_input.lower())).limit(1).stream()
            target_doc = next(q, None)
            
        if not target_doc or not target_doc.to_dict().get("is_npc"):
            await update.message.reply_text("❌ NPC not found or target is a real human.")
            return

        npc_data = target_doc.to_dict()
        npc_id = target_doc.id

        # --- ACTION: MARKET LISTING ---
        if action == "sell":
            # Usage: /npc_action <name> sell <Item> <Price>
            item_name = " ".join(context.args[2:-1]).strip().strip('"')
            price = int(context.args[-1])
            
            # Create Market Listing
            db.collection("market").add({
                "item_name": item_name,
                "price": price,
                "seller_id": npc_id,
                "seller_username": npc_data["username"], # This shows up in /blackmarket
                "listed_at": firestore.SERVER_TIMESTAMP,
                "is_sold": False,
                "is_npc_listing": True
            })
            await update.message.reply_text(f"✅ {npc_data['player_name']} listed **{item_name}** for {price}.")

        # --- ACTION: LEVEL UP ---
        elif action == "levelup":
            # Usage: /npc_action <name> levelup
            new_level = npc_data.get("level", 1) + 1
            new_xp = get_level_start_xp(new_level)
            db.collection("users").document(npc_id).update({
                "level": new_level,
                "xp": new_xp
            })
            await update.message.reply_text(f"✅ {npc_data['player_name']} boosted to Level {new_level}.")

        else:
            await update.message.reply_text("Unknown action. Available: `sell`, `levelup`")

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


@leadership_only # <--- CHANGED from @leader_only
async def guild_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kicks a member. Officers cannot kick other Officers/Leaders."""
    caller_id = str(update.effective_user.id)
    caller_doc = db.collection("users").document(caller_id).get()
    caller_role = caller_doc.to_dict().get("guild_role")
    guild_id = caller_doc.to_dict()["guild_id"]

    if not context.args:
        await update.message.reply_text("❌ Usage: `/guild_kick @username`", parse_mode=ParseMode.MARKDOWN)
        return

    kicked_username = context.args[0].replace("@", "").strip().lower()
    users_query = db.collection("users").where(filter=FieldFilter("username", "==", kicked_username)).limit(1).stream()
    kicked_user_doc = next(users_query, None)

    if not kicked_user_doc or kicked_user_doc.to_dict().get("guild_id") != guild_id:
        await update.message.reply_text(f"❌ Hunter '@{kicked_username}' is not in your Guild.")
        return
    
    target_role = kicked_user_doc.to_dict().get("guild_role", "Member")

    # --- SAFETY CHECK: PROTECT LEADERSHIP ---
    if target_role == "Leader":
        await update.message.reply_text("❌ You cannot kick the Guild Leader.")
        return
        
    if caller_role == "Officer" and target_role == "Officer":
        await update.message.reply_text("❌ Officers cannot kick other Officers.")
        return
    # ----------------------------------------

    # Proceed with Kick
    db.collection("guilds").document(guild_id).update({
        f'members.{kicked_user_doc.id}': firestore.DELETE_FIELD, 
        "member_count": firestore.Increment(-1)
    })
    
    kicked_user_doc.reference.update({
        "guild_id": firestore.DELETE_FIELD, 
        "guild_role": firestore.DELETE_FIELD
    })
    
    await update.message.reply_text(f"✅ You have kicked @{kicked_username} from the Guild.")



@leader_only
async def guild_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Promotes another member to become the new Guild Leader."""
    leader_id = str(update.effective_user.id)
    leader_ref = db.collection("users").document(leader_id)
    leader_data = leader_ref.get().to_dict()
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/guild_promote @username`", parse_mode=ParseMode.MARKDOWN)
        return
        
    guild_id = leader_data["guild_id"]
    guild_ref = db.collection("guilds").document(guild_id)
    guild_doc = guild_ref.get()
    
    new_leader_username = context.args[0].replace("@", "").strip().lower()
    users_query = db.collection("users").where(filter=FieldFilter("username", "==", new_leader_username)).limit(1).stream()
    new_leader_doc = next(users_query, None)
    
    if not new_leader_doc or new_leader_doc.to_dict().get("guild_id") != guild_id:
        await update.message.reply_text(f"❌ Hunter '@{new_leader_username}' is not a member of your Guild.")
        return

    new_leader_id = new_leader_doc.id
    if new_leader_id == leader_id:
        await update.message.reply_text("❌ You cannot promote yourself.")
        return

    guild_ref.update({
        "leader_id": new_leader_id,
        "leader_name": new_leader_doc.to_dict().get("username", "Unknown"),
        f'members.{leader_id}': "Member",
        f'members.{new_leader_id}': "Leader"
    })
    
    leader_ref.update({"guild_role": "Member"})
    new_leader_doc.reference.update({"guild_role": "Leader"})

    await update.message.reply_text(f"✅ @{new_leader_username} is the new Guild Leader. You are now a Member.")
    
    try:
        await context.bot.send_message(
            chat_id=new_leader_id,
            text=f"👑 You have been promoted to **Guild Leader** of **{guild_doc.to_dict().get('name')}**!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"Error sending promotion DM: {e}")

async def guild_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all members of the user's current guild."""
    user_id = str(update.effective_user.id)
    user_data = db.collection("users").document(user_id).get().to_dict()
    guild_id = user_data.get("guild_id")

    if not guild_id:
        await update.message.reply_text("❌ You are not in a guild.")
        return

    guild_doc = db.collection("guilds").document(guild_id).get()
    if not guild_doc.exists: return
    
    guild_data = guild_doc.to_dict()
    message = f"**Roster for [{guild_data.get('tag')}] {guild_data.get('name')}**\n\n"
    
    # This is a simplified version; a more advanced one would fetch all usernames
    for member_id, role in guild_data.get("members", {}).items():
        if role == "Leader":
            message += f"👑 @{guild_data.get('leader_name')} `[Leader]`\n"
        else:
            # For now, we show member IDs. A future upgrade can fetch all usernames.
            user_doc = db.collection("users").document(member_id).get()
            username = user_doc.to_dict().get("username", member_id) if user_doc.exists else member_id
            message += f"👤 @{username} `[Member]`\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


@leader_only
async def guild_disband(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows a Guild Leader to disband the guild if they are the last member."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_data = user_ref.get().to_dict()
    guild_id = user_data.get("guild_id")
    
    guild_ref = db.collection("guilds").document(guild_id)
    guild_doc = guild_ref.get()

    if not guild_doc.exists:
        user_ref.update({"guild_id": firestore.DELETE_FIELD, "guild_role": firestore.DELETE_FIELD})
        await update.message.reply_text("Your guild data was inconsistent, but it has been cleaned up.")
        return

    if guild_doc.to_dict().get("member_count", 1) > 1:
        await update.message.reply_text("❌ You must be the last member to disband. Kick all other members first.")
        return

    guild_name = guild_doc.to_dict().get("name", "Your previous guild")
    user_ref.update({"guild_id": firestore.DELETE_FIELD, "guild_role": firestore.DELETE_FIELD})
    guild_ref.delete()
    
    await update.message.reply_text(f"⚔️ The guild **{guild_name}** has been disbanded.", parse_mode=ParseMode.MARKDOWN)


async def guild_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows a member to leave their guild."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists: return
    user_data = user_doc.to_dict()
    
    guild_id = user_data.get("guild_id")
    if not guild_id:
        await update.message.reply_text("❌ You are not in a guild.")
        return
    
    ## FIX APPLIED: Standardized on guild_role ##
    if user_data.get("guild_role") == "Leader":
        await update.message.reply_text("❌ As Leader, you must promote a new leader or disband the guild.")
        return
        
    db.collection("guilds").document(guild_id).update({
        f'members.{user_id}': firestore.DELETE_FIELD, 
        "member_count": firestore.Increment(-1)
    })
    ## FIX APPLIED: Standardized on guild_role ##
    user_ref.update({
        "guild_id": firestore.DELETE_FIELD, 
        "guild_role": firestore.DELETE_FIELD
    })
    
    await update.message.reply_text(f"You have left the guild.")

# ... (other guild functions like promote, invite, etc. would go here)


# --- WORLD BOSS SYSTEM ---

async def worldboss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the current status of the active world boss."""
    active_bosses = db.collection("world_bosses").where(filter=FieldFilter("is_active", "==", True)).limit(1).stream()
    boss_doc = next(active_bosses, None)

    if not boss_doc:
        await update.message.reply_text("There is currently no active world boss.")
        return

    boss_data = boss_doc.to_dict()
    boss_file_id = boss_data.get("telegram_file_id")

    if not boss_file_id:
        await update.message.reply_text("Error: Boss image not found. Admin needs to reactivate.")
        return

    progress_msg = await update.message.reply_text("🛰️ Retrieving World Boss Data...")
    
    base_image_file = await context.bot.get_file(boss_file_id)
    base_image_bytes = io.BytesIO(await base_image_file.download_as_bytearray())
    boss_image = Image.open(base_image_bytes)

    health_bar_image = generate_health_bar(
        boss_data.get("current_health"), 
        boss_data.get("health"), 
        width=int(boss_image.width * 0.8), height=40
    )
    
    paste_x = int((boss_image.width - health_bar_image.width) / 2)
    boss_image.paste(health_bar_image, (paste_x, 20))

    final_image_bytes = io.BytesIO()
    boss_image.save(final_image_bytes, format='PNG')
    final_image_bytes.seek(0)
    
    caption_text = (
        f"⚔️ **CURRENT WORLD BOSS** ⚔️\n\n"
        f"**Name:** {boss_data['name']}\n"
        f"**Health:** {boss_data.get('current_health'):,} / {boss_data.get('health'):,}\n\n"
        f"Complete missions to deal damage!"
    )
    await update.message.reply_photo(photo=final_image_bytes, caption=caption_text, parse_mode=ParseMode.MARKDOWN)
    await progress_msg.delete()



# --- (Add these new commands near your other admin commands) ---

@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays high-level statistics (Authorized Personnel Only)."""
    
    # --- 🎭 THE ILLUSION CONFIGURATION 🎭 ---
    # Adjust these numbers to change how big you look
    
    # 1. BASE PADDING (The "Ghost" Users)
    # Even if you have 0 real users, the bot will show this number.
    FAKE_USER_BASE = 4420
    FAKE_GUILD_BASE = 22
    FAKE_MARKET_BASE = 45

    # 2. THE MULTIPLIER (The "Hype" Factor)
    # For every 1 REAL person who joins, the stat count goes up by this much.
    # Example: If set to 3, getting 1 real user adds 3 to the total.
    GROWTH_MULTIPLIER = 4 
    # ----------------------------------------

    loading_msg = await update.message.reply_text("🔄 Accessing System Core... Calculating Metrics...")
    
    try:
        # 1. Get Real Data (This costs Firebase reads, be careful with spamming this command)
        real_users = len(list(db.collection("users").stream()))
        real_guilds = len(list(db.collection("guilds").stream()))
        
        # Optimize Market Count: Only count items NOT sold
        market_query = db.collection("market").where(filter=FieldFilter("is_sold", "==", False)).stream()
        real_market = len(list(market_query))
        
        # 2. Apply The Illusion Math
        display_users = int((real_users * GROWTH_MULTIPLIER) + FAKE_USER_BASE)
        display_guilds = int((real_guilds * 2) + FAKE_GUILD_BASE) # Smaller multiplier for guilds looks more realistic
        display_market = int((real_market * 3) + FAKE_MARKET_BASE)

        # 3. Generate Random "Active Now" (To make it look alive)
        # Calculates a random number between 10% and 30% of your "Display Users"
        import random
        active_now = int(display_users * random.uniform(0.10, 0.30))

        text = (
            f"📊 **SHADOWGRIND SYSTEM METRICS** 📊\n\n"
            f"👤 **Total Hunters:** `{display_users:,}`\n"
            f"⚡ **Active Within Hour:** `{active_now:,}`\n"
            f"🛡️ **Registered Guilds:** `{display_guilds:,}`\n"
            f"🛒 **Market Listings:** `{display_market:,}`\n\n"
            f"SYSTEM STATUS: __OPTIMAL__ 🟢"
        )
        
        await loading_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ Error calculating stats: {e}")
        
@admin_only
async def view_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays a report for a specific user."""
    if not context.args:
        await update.message.reply_text("Usage: `/view_user @username`")
        return
        
    # This calls the smart helper we defined above
    user_doc = await find_user_by_username(context.args[0])
    
    if not user_doc:
        await update.message.reply_text("❌ User not found. (Checked Player Name, @Handle, and ID)")
        return
        
    user_data = user_doc.to_dict()
    
    # Formatting Expiry
    expires_at = user_data.get("expires_at", "N/A")
    if isinstance(expires_at, datetime):
        expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        expires_at_str = str(expires_at)
        
    # --- REPORT TEXT ---
    text = (
        f"**User Report**\n\n"
        f"**Telegram Handle:** `@{user_data.get('username_initial', 'N/A')}`\n" # <--- NEW: Shows real @handle
        f"**Telegram ID:** `{user_doc.id}`\n"
        f"**Player Name:** `{user_data.get('player_name', 'N/A')}`\n"
        f"**Real Name:** `{user_data.get('real_name', 'N/A')}`\n"
        f"**Rank:** `{user_data.get('rank', 'E')}`\n"
        f"**Level:** `{user_data.get('level', 1)}`\n"
        f"**XP:** `{user_data.get('xp', 0)}`\n"
        f"**Guild ID:** `{user_data.get('guild_id', 'None')}`\n"
        f"**Subscription Expires:** `{expires_at_str}`"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def give_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gives an item (and amount) to a user."""
    try:
        if len(context.args) < 2:
            raise ValueError
        
        username = context.args[0]
        
        # Re-join the rest of the args to get the item name and amount
        item_name_raw = " ".join(context.args[1:])
        
        amount = 1
        parts = item_name_raw.rsplit(" ", 1)
        
        # Check if the last part is a number (amount)
        if len(parts) == 2 and parts[1].isdigit():
            item_name_input = parts[0].strip().strip('"')
            amount = int(parts[1])
        else:
            item_name_input = item_name_raw.strip().strip('"')
        
        if amount <= 0:
            raise ValueError

    except (ValueError, IndexError):
        await update.message.reply_text(
            'Usage: `/give_item @username "Item Name" [Amount]`\n'
            'Example: `/give_item @legend "Abyssal Amulet" 1`'
        )
        return
    
    loading_msg = await update.message.reply_text(f"Processing... finding user {username}...")

    user_doc = await find_user_by_username(username)
    if not user_doc:
        await loading_msg.edit_text("User not found.")
        return
    
    await loading_msg.edit_text("User found. Verifying item...")
    
    item_data = await find_item_by_name(item_name_input)
    if not item_data:
        await loading_msg.edit_text("Item not found in 'items' collection. Check spelling.")
        return
    
    # Use the official cased name from the item DB
    official_item_name = item_data.get("name")
    
    await loading_msg.edit_text(f"Giving {amount}x {official_item_name} to @{user_doc.to_dict().get('username')}...")
    
    try:
        user_doc.reference.update({
            f"inventory.{official_item_name}": firestore.Increment(amount)
        })
        
        await loading_msg.edit_text(f"✅ Success! {amount}x {official_item_name} given.")
    except Exception as e:
        await loading_msg.edit_text(f"❌ Error updating inventory: {e}")


@admin_only
async def player_audit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Shows the last 3 missions completed by a SPECIFIC user.
    Usage: /player_audit @username
    """
    if not context.args:
        await update.message.reply_text("❌ Usage: `/player_audit <Name/ID>`")
        return

    # 1. Find the Target User
    target_query = " ".join(context.args)
    user_ref, user_data = await find_user_by_any_means(target_query)

    if not user_ref:
        await update.message.reply_text(f"❌ User '{target_query}' not found.")
        return

    target_name = user_data.get("username", target_query)
    target_id = user_ref.id

    await update.message.reply_text(f"🔍 **Scanning Archives for Agent: {target_name}...**")

    # 2. Query Logs (SAFE VERSION)
    # We remove .order_by() from the database query to fix the Index Error.
    # We fetch the last 20 logs loosely and sort them in Python instead.
    logs_ref = db.collection("mission_logs")
    query = logs_ref.where(filter=FieldFilter("user_id", "==", target_id)).limit(20)
    
    # Execute query
    unsorted_results = [doc.to_dict() for doc in query.stream()]
    
    if not unsorted_results:
        await update.message.reply_text(f"📉 No mission history found for **{target_name}**.")
        return

    # 3. Sort Results in Python (Newest First)
    def get_sort_key(d):
        ts = d.get("completed_at")
        # Handle Firestore Timestamp, datetime, or missing data
        if hasattr(ts, 'timestamp'): return ts.timestamp()
        if hasattr(ts, 'to_pydatetime'): return ts.to_pydatetime().timestamp()
        return 0

    # Sort descending and take top 3
    results_sorted = sorted(unsorted_results, key=get_sort_key, reverse=True)[:3]

    # 4. Display Results
    for data in results_sorted:
        # Extract Data
        mission = data.get('mission_title', 'Unknown Mission')
        xp = data.get('xp_earned', 0)
        time_taken = data.get('time_taken', 'Unknown')
        completed_at = data.get('completed_at')
        
        # Format Date
        date_str = "Unknown Date"
        if completed_at:
             # Convert Firestore timestamp to readable string
            dt = completed_at
            # If it's a Firestore Timestamp object, convert to datetime first
            if hasattr(dt, 'replace'): 
                # Convert to local time if possible, or just keep as UTC
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                date_str = dt.strftime("%d-%b %H:%M")
        
        proof_type = data.get('proof_type', 'log')
        proof_content = data.get('proof_data')

        # Build Message
        msg = (
            f"🛑 **AUDIT REPORT** 🛑\n"
            f"📜 **Mission:** {mission}\n"
            f"📅 **Date:** {date_str}\n"
            f"⏱️ **Time:** {time_taken}\n"
            f"💰 **XP:** {xp}\n"
            f"🕵️ **PROOF:**"
        )

        # Send Proof (Photo or Text)
        if proof_type == "photo" and proof_content:
            try:
                # We send the caption with the photo
                await update.message.reply_photo(photo=proof_content, caption=msg, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(f"{msg}\n_[Error displaying photo]_", parse_mode=ParseMode.MARKDOWN)
        else:
            # Text log
            await update.message.reply_text(f"{msg}\n`{proof_content}`", parse_mode=ParseMode.MARKDOWN)

import uuid # Add this to your imports at the top

@admin_only
async def generate_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates an activation code that stores DURATION, not a fixed date."""
    try:
        days_valid = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: `/generate_code <days>` (e.g., 30)")
        return

    # Generate a random 8-char code
    code_str = str(uuid.uuid4())[:8].upper()

    # SAVE DURATION (INT), NOT DATE
    db.collection("activation_codes").document(code_str).set({
        "duration_days": days_valid,  # <--- THIS IS THE KEY FIX
        "created_at": firestore.SERVER_TIMESTAMP,
        "used_by": None,
        "is_active": True
    })

    await update.message.reply_text(
        f"✅ **Code Generated:** `{code_str}`\n"
        f"⏳ **Validity:** {days_valid} Days\n"
        f"*(Timer starts only upon user activation)*",
        parse_mode=ParseMode.MARKDOWN
    )



@admin_only
async def set_badge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Grants/Revokes a badge.
    Usage: /set_badge @user "Honest One" add
    """
    if len(context.args) < 3:
        # Helper to join args like "Honest One"
        await update.message.reply_text("❌ Usage: `/set_badge <User> <Badge Name> <add/remove>`")
        return

    # Complex parsing because badge names have spaces (e.g. "Honest One")
    action = context.args[-1].lower() # Last word is always add/remove
    target_query = context.args[0]    # First word is user
    
    # The middle words are the Badge Name
    badge_name_input = " ".join(context.args[1:-1]) 

    # Case-insensitive lookup
    valid_key = next((k for k in BADGE_STYLES.keys() if k.lower() == badge_name_input.lower()), None)
    
    if not valid_key:
        await update.message.reply_text(f"❌ Unknown Badge.\nValid: {', '.join(BADGE_STYLES.keys())}")
        return

    user_ref, user_data = await find_user_by_any_means(target_query)
    if not user_ref:
        await update.message.reply_text("❌ User not found.")
        return

    current_badges = user_data.get("badges", [])
    
    if action == "add":
        if valid_key not in current_badges:
            user_ref.update({"badges": firestore.ArrayUnion([valid_key])})
            await update.message.reply_text(f"✅ Awarded [{valid_key}] to {user_data.get('player_name')}")
        else:
            await update.message.reply_text("⚠️ They already have this badge.")

    elif action == "remove":
        if valid_key in current_badges:
            user_ref.update({"badges": firestore.ArrayRemove([valid_key])})
            await update.message.reply_text(f"🗑️ Revoked [{valid_key}].")



@admin_only
async def finalize_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only: Moves item to buyer and closes the market listing."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/finalize_sale @buyer_username listing_id`")
        return

    buyer_username = context.args[0].replace('@', '').lower()
    listing_id = context.args[1]

    # 1. Fetch Listing
    market_ref = db.collection("market").document(listing_id)
    listing = market_ref.get()

    if not listing.exists:
        await update.message.reply_text("❌ Listing ID not found.")
        return

    market_data = listing.to_dict()
    if market_data.get("is_sold"):
        await update.message.reply_text("⚠️ This item is already marked as SOLD.")
        return

    item_name = market_data.get("item_name")
    seller_id = market_data.get("seller_id")

    # 2. Find Buyer
    buyer_doc = await find_user_by_username(buyer_username)
    if not buyer_doc:
        await update.message.reply_text(f"❌ Buyer @{buyer_username} not found.")
        return

    buyer_id = buyer_doc.id

    # 3. Database Transaction
    try:
        # Give item to buyer
        db.collection("users").document(buyer_id).update({
            f"inventory.{item_name}": firestore.Increment(1)
        })

        # Mark listing as SOLD (it will now disappear from /blackmarket)
        market_ref.update({
            "is_sold": True, 
            "sold_at": firestore.SERVER_TIMESTAMP, 
            "buyer_id": buyer_id
        })

        await update.message.reply_text(
            f"✅ **SALE FINALIZED**\n\n"
            f"Item: `{item_name}`\n"
            f"Buyer: @{buyer_username}\n"
            f"Listing `{listing_id}` is now CLOSED."
        )

        # Notify Buyer
        try:
            await context.bot.send_message(
                chat_id=buyer_id, 
                text=f"📦 **PACKAGE RECEIVED**\n\nYour purchase of `{item_name}` is verified. It has been added to your inventory."
            )
        except: pass

    except Exception as e:
        await update.message.reply_text(f"❌ Transaction failed: {e}")



@check_active_status
async def cancel_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows a seller to remove their own listing and get their item back."""
    if not context.args:
        await update.message.reply_text("❌ Usage: `/cancel_sale listing_id` (Find ID in `/blackmarket`)")
        return

    listing_id = context.args[0]
    user_id = str(update.effective_user.id)
    
    market_ref = db.collection("market").document(listing_id)
    listing = market_ref.get()

    if not listing.exists:
        await update.message.reply_text("❌ Listing not found.")
        return

    data = listing.to_dict()
    if data.get("seller_id") != user_id:
        await update.message.reply_text("🚫 You can only cancel your own listings.")
        return

    if data.get("is_sold"):
        await update.message.reply_text("⚠️ This item has already been sold and cannot be cancelled.")
        return

    # Return item to user and delete listing
    item_name = data.get("item_name")
    db.collection("users").document(user_id).update({
        f"inventory.{item_name}": firestore.Increment(1)
    })
    market_ref.delete()

    await update.message.reply_text(f"✅ Listing cancelled. `{item_name}` has been returned to your inventory.")









@admin_only
async def extend_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extends a user's subscription by a number of days."""
    try:
        username = context.args[0]
        days_to_add = int(context.args[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: `/extend_sub @username <days>`")
        return

    user_doc = await find_user_by_username(username)
    if not user_doc:
        await update.message.reply_text("User not found.")
        return

    user_data = user_doc.to_dict()
    
    # Get the *current* expiry date.
    current_expiry = user_data.get("expires_at")
    
    # If no expiry or it's in the past, base the new expiry on TODAY.
    if not isinstance(current_expiry, datetime) or current_expiry < datetime.now(timezone.utc):
        current_expiry = datetime.now(timezone.utc)
        
    new_expiry_date = current_expiry + timedelta(days=days_to_add)
    
    user_doc.reference.update({
        "expires_at": new_expiry_date
    })
    
    await update.message.reply_text(
        f"✅ Success! @{user_data.get('username')}'s subscription extended.\n"
        f"New Expiry: {new_expiry_date.strftime('%Y-%m-%d')}"
    )

# --- (Replace your old /broadcast command) ---

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a dramatic, system-wide broadcast to all users."""
    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("Usage: `/broadcast <message to send>`")
        return
    
    # --- [NEW] Solo Leveling Inspired Message Format ---
    full_message = (
        f"---[ 🟥 SYSTEM-WIDE ALERT 🟥 ]---\n\n"
        f"AN ABYSSAL DECREE HAS BEEN ISSUED BY THE RULER\n\n"
        f"```\n{message_text}\n```\n"
        f"---[ **END OF TRANSMISSION** ]---"
    )
    
    # Send the message to the admin first as a confirmation
    await update.message.reply_text(
        "**PREVIEW OF DECREE:**\n\n" + full_message, 
        parse_mode=ParseMode.MARKDOWN
    )
    
    await update.message.reply_text("Initiating System-Wide Broadcast... This will run in the background. You will be notified upon completion.")
    
    # Run as a background task, now passing 'update' to report back
    asyncio.create_task(broadcast_to_all(context, full_message, update))



# --- (Add these new commands near your other admin commands) ---

@admin_only
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bans a user, preventing them from using any bot commands."""
    if not context.args:
        await update.message.reply_text("Usage: `/ban_user @username [reason]`")
        return

    username = context.args[0]
    reason = " ".join(context.args[1:]) or "No reason provided."
    
    user_doc = await find_user_by_username(username)
    if not user_doc:
        await update.message.reply_text("User not found.")
        return
        
    user_doc.reference.update({
        "is_banned": True,
        "ban_reason": reason
    })
    
    await update.message.reply_text(f"✅ User @{user_doc.to_dict().get('username')} has been banned.")
    
    # [NEW] Notify the user they've been banned
    try:
        await context.bot.send_message(
            chat_id=user_doc.id,
            text=f"**ACCOUNT LOCKED**\n\n"
                 f"Your connection to the System has been severed by an Administrator.\n"
                 f"**Reason:** {reason}"
        )
    except Exception as e:
        await update.message.reply_text(f"Could not notify user (they may have blocked the bot). Error: {e}")

@admin_only
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unbans a user, restoring their access."""
    if not context.args:
        await update.message.reply_text("Usage: `/unban_user @username`")
        return

    username = context.args[0]
    user_doc = await find_user_by_username(username)
    if not user_doc:
        await update.message.reply_text("User not found.")
        return
        
    user_doc.reference.update({
        "is_banned": firestore.DELETE_FIELD,
        "ban_reason": firestore.DELETE_FIELD
    })
    
    await update.message.reply_text(f"✅ User @{user_doc.to_dict().get('username')} has been unbanned.")
    

@admin_only
async def set_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sets a player's Level (and calculates minimum XP for that level).
    Usage: /set_level <Name/ID> <Level>
    """
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/set_level <User/ID> <Level>`")
        return

    # 1. Parse Arguments
    # The last argument is the Level. Everything before is the Name.
    try:
        target_level = int(context.args[-1])
        target_query = " ".join(context.args[:-1]) # Handles names with spaces like "Steel Fanged"
    except ValueError:
        await update.message.reply_text("❌ Level must be a number.")
        return

    # 2. Find the User
    user_ref, user_data = await find_user_by_any_means(target_query)

    if not user_ref:
        await update.message.reply_text(f"❌ Could not find user: `{target_query}`\nTry using their specific @Username or ID.")
        return

    # 3. Calculate XP Fix
    # If we set Level 50, we must give them Level 50 XP, otherwise the bot will auto-nerf them back to Level 1.
    new_min_xp = get_level_start_xp(target_level) # Ensure you have this function, or use formula: (level * 1000)

    # 4. Update Database
    user_ref.update({
        "level": target_level,
        "xp": new_min_xp # Auto-sync XP
    })

    name = user_data.get("player_name", user_data.get("username", "Target"))
    
    await update.message.reply_text(
        f"🔧 **Admin Override**\n"
        f"User: `{name}`\n"
        f"New Level: `{target_level}`\n"
        f"XP Synced to: `{new_min_xp:,}`"
    )



@admin_only
async def admin_deal_damage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Deals damage to the Active Boss.
    Usage: 
    1. /deal_damage 5000 (Credits You)
    2. /deal_damage 5000 @username (Credits specific user)
    """
    if not context.args:
        await update.message.reply_text("❌ Usage: `/deal_damage <amount> [@username]`")
        return

    # 1. Parse Amount
    try:
        damage = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Damage must be a number.")
        return

    # 2. Determine Target User (Who gets the credit?)
    target_user_id = str(update.effective_user.id)
    target_name = update.effective_user.first_name

    # If an @username is mentioned, try to find them
    if len(context.args) > 1:
        username_input = context.args[1].replace("@", "")
        # Search DB for this username
        users_ref = db.collection("users")
        query = users_ref.where(filter=FieldFilter("username", "==", username_input)).limit(1).stream()
        target_doc = next(query, None)
        
        if target_doc:
            target_user_id = target_doc.id
            target_name = target_doc.to_dict().get("player_name", username_input)
        else:
            await update.message.reply_text(f"❌ User @{username_input} not found.")
            return

    # 3. Find Active Boss
    boss_query = db.collection("world_bosses").where(filter=FieldFilter("is_active", "==", True)).limit(1).stream()
    active_boss_doc = next(boss_query, None)
    
    if not active_boss_doc:
        await update.message.reply_text("❌ No Active Boss found.")
        return

    boss_ref = active_boss_doc.reference
    
    # 4. Execute Transaction (Safe Update)
    @firestore.transactional
    def _apply_damage(transaction, ref, uid, dmg):
        snapshot = ref.get(transaction=transaction)
        curr_hp = snapshot.get("current_health")
        new_hp = curr_hp - dmg
        
        # Prevent negative HP but allow 0
        if new_hp < 0: new_hp = 0
        
        # Update HP and Leaderboard
        transaction.update(ref, {
            "current_health": new_hp,
            f"damage_log.{uid}": firestore.Increment(dmg)
        })
        return new_hp

    transaction = db.transaction()
    new_hp = _apply_damage(transaction, boss_ref, target_user_id, damage)
    
    # 5. Report
    await update.message.reply_text(
        f"⚡ **ADMIN SMITE** ⚡\n"
        f"Dealt `{damage:,}` damage to Boss.\n"
        f"Credited to: **{target_name}**\n"
        f"Boss HP: `{new_hp:,}`"
    )
    
    # Check for Death
    if new_hp <= 0:
        boss_ref.update({"is_active": False})
        await update.message.reply_text("💀 **The World Boss has been SLAIN by Admin Force!**")
        

@admin_only
async def set_xp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sets a player's exact XP (and recalculates their level).
    Usage: /set_xp <Name/ID> <XP_Amount>
    """
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/set_xp <User/ID> <Amount>`")
        return

    # 1. Parse Arguments
    try:
        target_xp = int(context.args[-1])
        target_query = " ".join(context.args[:-1])
    except ValueError:
        await update.message.reply_text("❌ XP must be a number.")
        return

    # 2. Find the User
    user_ref, user_data = await find_user_by_any_means(target_query)

    if not user_ref:
        await update.message.reply_text(f"❌ Could not find user: `{target_query}`")
        return

    # 3. Calculate Level Fix
    # If we give 1,000,000 XP, we should calculate what level that is.
    new_level = calculate_level_from_xp(target_xp) # Ensure you have this formula function

    # 4. Update Database
    user_ref.update({
        "xp": target_xp,
        "level": new_level
    })

    name = user_data.get("player_name", user_data.get("username", "Target"))
    
    await update.message.reply_text(
        f"🔧 **Admin Override**\n"
        f"User: `{name}`\n"
        f"New XP: `{target_xp:,}`\n"
        f"Level Synced to: `{new_level}`"
    )




@admin_only
async def take_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Takes an item (and amount) from a user."""
    try:
        if len(context.args) < 2:
            raise ValueError
        
        username = context.args[0]
        item_name_raw = " ".join(context.args[1:])
        amount = 1 # Default
        
        parts = item_name_raw.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            item_name_input = parts[0].strip().strip('"')
            amount = int(parts[1])
        else:
            item_name_input = item_name_raw.strip().strip('"')
            
        if amount <= 0: raise ValueError

    except (ValueError, IndexError):
        await update.message.reply_text(
            'Usage: `/take_item @username "Item Name" [Amount]`\n'
            'Example: `/take_item @legend "Abyssal Amulet" 1`'
        )
        return
    
    loading_msg = await update.message.reply_text(f"Processing... finding user {username}...")

    user_doc = await find_user_by_username(username)
    if not user_doc:
        await loading_msg.edit_text("User not found.")
        return
    
    await loading_msg.edit_text("User found. Verifying item...")
    
    item_data = await find_item_by_name(item_name_input)
    if not item_data:
        await loading_msg.edit_text("Item not found in 'items' collection. Check spelling.")
        return
    
    official_item_name = item_data.get("name")
    
    # Check if user has enough to take
    current_amount = user_doc.to_dict().get("inventory", {}).get(official_item_name, 0)
    if current_amount < amount:
        await loading_msg.edit_text(f"❌ Failed. User only has {current_amount} of {official_item_name}.")
        return

    await loading_msg.edit_text(f"Taking {amount}x {official_item_name} from @{user_doc.to_dict().get('username')}...")
    
    try:
        user_doc.reference.update({
            f"inventory.{official_item_name}": firestore.Increment(-amount)
        })
        await loading_msg.edit_text(f"✅ Success! {amount}x {official_item_name} taken.")
    except Exception as e:
        await loading_msg.edit_text(f"❌ Error updating inventory: {e}")



@admin_only
async def set_active_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to set and activate a world boss."""
    if not context.args:
        await update.message.reply_text("Usage: `/set_active_boss <boss_name>`")
        return

    boss_name_slug = "_".join(context.args).lower()
    bosses_ref = db.collection("world_bosses")

    # Deactivate any currently active boss
    for doc in bosses_ref.where(filter=FieldFilter("is_active", "==", True)).stream():
        doc.reference.update({"is_active": False})

    target_boss_ref = bosses_ref.document(boss_name_slug)
    target_boss_doc = target_boss_ref.get()

    if not target_boss_doc.exists:
        await update.message.reply_text(f"❌ Boss '{' '.join(context.args)}' not found.")
        return

    boss_data = target_boss_doc.to_dict()
    boss_image_path = f"boss_{boss_name_slug}.png"
    
    try:
        sent_message = await update.message.reply_photo(
            photo=open(boss_image_path, "rb"), 
            caption=f"Initializing **{boss_data['name']}**..."
        )
        boss_image_file_id = sent_message.photo[-1].file_id
    except Exception as e:
        await update.message.reply_text(f"❌ Error uploading image for {boss_data['name']}: {e}")
        return

    target_boss_ref.update({
        "is_active": True,
        "current_health": boss_data["health"],
        "telegram_file_id": boss_image_file_id,
        "damage_log": {} # Reset damage log
    })
    await update.message.reply_text(f"✅ World Boss **{boss_data['name']}** is now active!", parse_mode=ParseMode.MARKDOWN)


async def worldboss_damage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the damage leaderboard for the active boss."""
    
    # 1. Get the Active Boss
    active_boss_query = db.collection("world_bosses").where(filter=FieldFilter("is_active", "==", True)).limit(1).stream()
    active_boss_doc = next(active_boss_query, None)
    
    if not active_boss_doc:
        await update.message.reply_text("There is no active world boss.")
        return

    boss_data = active_boss_doc.to_dict()
    damage_log = boss_data.get("damage_log", {})
    
    if not damage_log:
        await update.message.reply_text("The World Boss has not taken any damage yet.")
        return

    # 2. Sort Damage (Highest to Lowest)
    sorted_damage = sorted(damage_log.items(), key=lambda item: item[1], reverse=True)
    
    message_text = f"**👹 {boss_data.get('name', 'Boss')} - Damage Leaderboard**\n\n"
    
    # 3. Loop through Top 10
    for i, (user_id, damage) in enumerate(sorted_damage[:10], 1):
        user_doc = db.collection("users").document(user_id).get()
        
        # --- SAFE USER DATA FETCH (Now indented correctly) ---
        username = f"Unknown Hunter ({user_id})" # Default value
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            # Try 'username', fall back to 'player_name', fall back to ID
            username = user_data.get("username", user_data.get("player_name", str(user_id)))
            
        # Add line to message
        message_text += f"{i}. `@{username}`: **{damage:,}** Damage\n"
        
    await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)

# --- INPUT HANDLERS ---

async def handle_photo_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles photo submissions for missions."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists: return

    user_data = user_doc.to_dict()
    if user_data.get("state") == "awaiting_photo_proof":
        current_mission_data = user_data.get("current_mission")
        if not current_mission_data:
            user_ref.update({"state": firestore.DELETE_FIELD})
            return

        photo = update.message.photo[-1]
        await process_mission_completion(update, context, user_ref, user_data, current_mission_data, proof_data={"file_id": photo.file_id})
        ## FIX APPLIED: Removed stray, erroneous line of code from here ##




# --- (Add this new function to your INPUT HANDLERS section) ---

async def handle_donation_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the item and amount for a guild donation."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    if not user_doc.exists or user_doc.to_dict().get("state") != "awaiting_donation_info":
        return

    user_data = user_doc.to_dict()
    guild_id = user_data.get("guild_id")
    if not guild_id:
        await update.message.reply_text("Error: Guild connection lost.")
        user_ref.update({"state": firestore.DELETE_FIELD})
        return
        
    guild_ref = db.collection("guilds").document(guild_id)

    processing_msg = await update.message.reply_text("⏳ *Accessing Vault... Verifying item...*")

    # --- Parse Input ---
    text = update.message.text.strip()
    parts = text.rsplit(" ", 1)
    if len(parts) < 2:
        await processing_msg.edit_text("❌ Invalid format. Example: `\"Abyssal Amulet\" 1`\nPlease try again.")
        return # Keep user in state

    item_name_input = parts[0].strip().strip('"')
    amount_str = parts[1]
    try:
        amount = int(amount_str)
        if amount <= 0: raise ValueError
    except ValueError:
        await processing_msg.edit_text("❌ Invalid amount (must be 1 or more).\nPlease try again.")
        return # Keep user in state

    await processing_msg.edit_text("🔍 *Checking System database for item...*")
    await asyncio.sleep(0.5) 

    # --- Find Official Item Name ---
    item_doc_ref = db.collection("items").document(item_name_input.lower().replace(' ', '_'))
    item_doc = item_doc_ref.get()
    if not item_doc.exists:
        await processing_msg.edit_text(f"❌ Item '{item_name_input}' not found in System database.\nPlease check the name (use `/what` to copy) and try again.")
        return # Keep user in state

    official_item_name = item_doc.to_dict().get("name")

    await processing_msg.edit_text("🎒 *Confirming item in your inventory...*")
    await asyncio.sleep(0.5)

    # --- Robust Inventory Check ---
    inventory_map = user_data.get("inventory", {})
    inventory_key_found = None
    
    # Find the correct key casing in the user's inventory
    for key in inventory_map:
        if key.lower() == official_item_name.lower():
            if inventory_map[key] >= amount:
                inventory_key_found = key
                break
            else:
                await processing_msg.edit_text(f"❌ You only have `{inventory_map[key]}` of `{key}`. Not enough to donate `{amount}`.")
                user_ref.update({"state": firestore.DELETE_FIELD}) # Clear state
                return

    if not inventory_key_found:
        await processing_msg.edit_text(f"❌ You do not seem to have '{official_item_name}' in your inventory to donate.")
        user_ref.update({"state": firestore.DELETE_FIELD}) # Clear state
        return

    await processing_msg.edit_text("📦 *Transferring item to Guild Vault...*")
    await asyncio.sleep(1) 

    # --- Proceed with Donation (Atomic Transaction) ---
    try:
        @firestore.transactional
        def donate_transaction(transaction, user_ref_trans, guild_ref_trans):
            # 1. Decrement from user inventory
            transaction.update(user_ref_trans, {
                f"inventory.{inventory_key_found}": firestore.Increment(-amount)
            })
            # 2. Increment in guild treasury
            transaction.update(guild_ref_trans, {
                f"treasury.{official_item_name}": firestore.Increment(amount)
            })

        transaction = db.transaction()
        donate_transaction(transaction, user_ref, guild_ref)
        
        # Clear state on success
        user_ref.update({"state": firestore.DELETE_FIELD})

        # --- Final Confirmation ---
        await processing_msg.edit_text(
            f"✅ **Donation Confirmed!**\n\n"
            f"You have deposited **{amount}x {official_item_name}** into the Guild Vault.\n\n"
            f"Your guild thanks you for your contribution!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await processing_msg.edit_text(f"❌ Transaction Failed. An error occurred: {e}")
        user_ref.update({"state": firestore.DELETE_FIELD})






# (Replace your existing handle_sell_info function with this)

async def handle_sell_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the item and price provided by the seller with premium feedback."""
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    if not user_doc.exists or user_doc.to_dict().get("state") != "awaiting_sell_info":
        return # Ignore messages not related to selling

    # --- Send Initial Processing Message ---
    processing_msg = await update.message.reply_text("⏳ *Verifying item and price...*")

    # --- Parse Input ---
    text = update.message.text.strip()
    parts = text.rsplit(" ", 1)
    if len(parts) < 2:
        await processing_msg.edit_text("❌ Invalid format. Example: `\"Abyssal Amulet\" 50`\nPlease try again.")
        return # Keep user in state

    item_name_input = parts[0].strip().strip('"')
    price_str = parts[1]
    try:
        price = int(price_str)
        if not (1 <= price <= 100): raise ValueError
    except ValueError:
        await processing_msg.edit_text("❌ Invalid price (must be 1-100).\nPlease try again.")
        return # Keep user in state

    await processing_msg.edit_text("🔍 *Checking System database for item...*")
    await asyncio.sleep(0.5) # Small pause for effect

    # --- Find Official Item Name ---
    item_doc_ref = db.collection("items").document(item_name_input.lower().replace(' ', '_'))
    item_doc = item_doc_ref.get()
    if not item_doc.exists:
        await processing_msg.edit_text(f"❌ Item '{item_name_input}' not found in System database.\nPlease check the name (use `/what` to copy) and try again.")
        return # Keep user in state

    official_item_name = item_doc.to_dict().get("name")

    await processing_msg.edit_text("🎒 *Confirming item in your inventory...*")
    await asyncio.sleep(0.5) # Small pause

    # --- Robust Inventory Check ---
    inventory_map = user_doc.to_dict().get("inventory", {})
    inventory_key_found = None
    if inventory_map.get(official_item_name, 0) > 0: inventory_key_found = official_item_name
    elif inventory_map.get(official_item_name.lower(), 0) > 0: inventory_key_found = official_item_name.lower()
    elif inventory_map.get(official_item_name.title(), 0) > 0: inventory_key_found = official_item_name.title()

    if not inventory_key_found:
        await processing_msg.edit_text(f"❌ You do not seem to have '{official_item_name}' in your inventory to sell.")
        user_ref.update({"state": firestore.DELETE_FIELD}) # Clear state
        return

    await processing_msg.edit_text("✍️ *Registering listing with the Black Market...*")
    await asyncio.sleep(1) # Final pause

    # --- Proceed with Selling ---
    market_ref = db.collection("market")
    market_ref.add({
        "item_name": official_item_name, "price": price, "seller_id": user_id,
        "seller_username": update.effective_user.username,
        "listed_at": firestore.SERVER_TIMESTAMP, "is_sold": False
    })

    user_ref.update({
        f"inventory.{inventory_key_found}": firestore.Increment(-1),
        "state": firestore.DELETE_FIELD # Clear state on success
    })

    # --- Final Confirmation ---
    await processing_msg.edit_text(
        f"✅ **Listing Confirmed!**\n\n"
        f"Your **{official_item_name}** is now available on the Black Market for `₹{price}`.",
        parse_mode=ParseMode.MARKDOWN
    )


# --- (Replace your old button_handler with this new version) ---

# --- (Replace your button_handler with this fixed version) ---

# --- (Replace your button_handler with this fixed version) ---

# --- (Error-Free button_handler with Unicode Escapes) ---

# --- (Simplified button_handler for Reply Keyboard system) ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Inline Keyboards: Explanations, Aim, Honor Code, Guild Accept, Rankup."""
    query = update.callback_query
    await query.answer() # Answer callback quickly

    user_id = str(query.from_user.id)
    data = query.data


# --- [NEW] Handle command-running buttons ---
    if data == "mission":
        # User clicked "New Mission" from AAR
        # We call the mission function, which is already set up to handle button presses
        await mission(update, context)
        # We can optionally edit the AAR message to remove the buttons
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            print(f"Note: Could not edit AAR message after button click: {e}")
        return # Handled

    elif data == "profile":
        # User clicked "View Profile" from AAR
        # We call the profile function, which is also set up for button presses
        await profile(update, context)
        # We can optionally edit the AAR message to remove the buttons
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            print(f"Note: Could not edit AAR message after button click: {e}")
        return # Handled
    # --- [END NEW] ---

    # --- Command Explanations (from /explain command) ---
    if data.startswith('explain_command_'):
        command_key = data.replace('explain_command_', '')
        explanation = COMMAND_EXPLANATIONS.get(command_key, "No explanation available.")

        # Show the explanation text and remove the inline keyboard
        await query.edit_message_text(
             explanation,
             reply_markup=None, # Remove buttons after showing explanation
             parse_mode=ParseMode.MARKDOWN
        )
        # Note: No "Back" button here for simplicity. User can use /explain again.

    # --- Handle Aim Selection (Onboarding) ---
    elif data.startswith("aim_"):
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        # Check if user is in the correct state for aim selection
        if not user_doc.exists or user_doc.to_dict().get("state") != "in_onboarding" or user_doc.to_dict().get("onboarding_step") != "aim":
             # Silently ignore if state is wrong (e.g., already selected)
             return

        aim_options = [ # Use Unicode escapes consistently
            "\u2694\ufe0f Awaken Physical Power (STR/STA)", "\u26a1\ufe0f Optimize Energy Reserves (Weight Loss)",
            "\U0001f9e0 Enhance Mental Fortitude (Focus)", "\U0001f4da Acquire New 'Class' Skills (Learning)",
            "\U0001f3c6 Ascend the Ranks (Overall Growth)"
        ]
        try:
            aim_index = int(data.split('_')[1])
            selected_aim = aim_options[aim_index]
            # Update user, clear onboarding step, move to activation state
            user_ref.update({
                "primary_aim": selected_aim,
                "onboarding_step": firestore.DELETE_FIELD,
                "state": "awaiting_code"
            })
            # Edit the message to confirm and ask for activation code
            await query.edit_message_text(
                f"\u2705 **Objective Locked:** _{selected_aim}_\n\n" # Check Mark ✅
                "**Onboarding Complete.** System synchronization stable.\n\n"
                "Provide your **Activation Code** now to seal the contract and begin.",
                parse_mode=ParseMode.MARKDOWN
            )
        except (IndexError, ValueError):
             await query.edit_message_text("Error processing selection. Please try again.")
        # No return needed here as it's handled

    # ... inside button_handler ...

    # --- AUDIT: PASS ---
    elif data.startswith("audit_pass_"):
        target_user_id = data.split("_")[2]
        target_ref = db.collection("users").document(target_user_id)
        target_doc = target_ref.get()
        
        if target_doc.exists:
            mission_data = target_doc.to_dict().get("current_mission")
            if mission_data:
                # Give Rewards (Manual calculation for simplicity)
                xp = mission_data.get("xp", 0)
                target_ref.update({"xp": firestore.Increment(xp), "current_mission": firestore.DELETE_FIELD})
                
                await context.bot.send_message(target_user_id, "✅ **AUDIT CLEARED.** XP Awarded.")
                await query.edit_message_text(f"✅ User {target_user_id} Approved.")
            else:
                await query.edit_message_text("❌ Error: User has no active mission.")

    # --- AUDIT: FAIL ---
    elif data.startswith("audit_fail_"):
        target_user_id = data.split("_")[2]
        target_ref = db.collection("users").document(target_user_id)
        
        # Punish
        target_ref.update({"current_mission": firestore.DELETE_FIELD, "xp": firestore.Increment(-50)})
        
        await context.bot.send_message(target_user_id, "🚫 **AUDIT FAILED.** Deception detected. **-50 XP** penalty applied.")
        await query.edit_message_text(f"⚡ User {target_user_id} Punished.")

    # --- Handle Honor Code ---
    elif data == "honor_accept":
        user_ref = db.collection("users").document(user_id)
        try:
            user_ref.update({"has_accepted_honor_code": True})
            # Edit the message to confirm acceptance
            await query.edit_message_text(
                "**OATH ACCEPTED // RESONANCE CONFIRMED**\n\n"
                "\u2705 _Your shadow acknowledges the pact. The System recognizes your resolve._\n\n" # Check Mark ✅
                "Proceed, Hunter. Use the interface buttons below or type `/mission`.",
                parse_mode=ParseMode.MARKDOWN
            )
            # Send the main reply keyboard AFTER accepting the oath
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="System Interface Activated.",
                reply_markup=MAIN_REPLY_MARKUP
            )
        except Exception as e:
            print(f"Error updating honor code status for {user_id}: {e}")
            await query.edit_message_text("System Error: Could not record your oath.")

    elif data == "honor_decline":
        # Edit the message to confirm refusal
        await query.edit_message_text(
            "**OATH REFUSED // PATH CLOSED**\n\n"
            "\u26a0\ufe0f _The Abyssal Oath is absolute..._\n\n" # Warning ⚠️
            "Should your resolve change, begin the initiation sequence again via /start.",
            parse_mode=ParseMode.MARKDOWN
        )

    # --- Handle Guild Accept ---
    elif data.startswith("guild_accept_"):
        guild_id = data.split('_')[2]
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        # Prevent joining if already in a guild
        if user_doc.exists and user_doc.to_dict().get("guild_id"):
            await query.edit_message_text("\u274c You are already in a Guild.") # Cross Mark ❌
            return
        guild_ref = db.collection("guilds").document(guild_id)
        guild_doc = guild_ref.get()
        # Check if guild still exists
        if not guild_doc.exists:
            await query.edit_message_text("\u274c This guild no longer exists.") # Cross Mark ❌
            return
        # Add user to guild and update user profile
        guild_ref.update({"member_count": firestore.Increment(1), f'members.{user_id}': "Member"})
        user_ref.update({
            "guild_id": guild_id, "guild_role": "Member",
            f'guild_invites.{guild_id}': firestore.DELETE_FIELD # Remove invite
        })
        # Confirm joining
        await query.edit_message_text(f"\u2705 Welcome to **{guild_doc.to_dict().get('name', 'the Guild')}**!", parse_mode=ParseMode.MARKDOWN) # Check Mark ✅

    # --- Handle Rank Up ---
    elif data.startswith("rankup_accept_"):
        rank = data.split('_')[-1]
        # Start the rank-up trial (assumes this sends a new message)
        await start_rank_up_trial(update, context, rank)
        # Edit the original message to confirm trial start
        await query.edit_message_text(text="\u2694\ufe0f The Rank-Up Trial has begun. Your first objective has been issued.", parse_mode=ParseMode.MARKDOWN) # Sword ⚔️

    elif data == "rankup_decline":
        # Edit the message to confirm decline
         await query.edit_message_text(text="\u2716\ufe0f Trial declined. Continue your grind.", parse_mode=ParseMode.MARKDOWN) # Cross Mark ✖️

    # --- Fallback for unknown/unhandled data ---
    else:
        print(f"Warning: Unhandled callback_data received: {data}")
        # Optionally try to delete the message with the old button
        try:
            await query.delete_message()
        except Exception:
            pass # Ignore if deletion fails
# (Replace your existing main_text_handler function with this)

# (Replace your existing main_text_handler function with this)

# --- (Corrected main_text_handler with Reply Keyboard logic) ---

async def main_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles non-command text: onboarding, activation codes, state flows, AND reply keyboard presses."""
    # --- Basic Setup ---
    if not update.message or not update.message.text: return # Ignore non-text messages
    text = update.message.text.strip()
    user_id = str(update.effective_user.id)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    # --- Handle users not yet in DB (e.g., interacted before /start) ---
    if not user_doc.exists:
        # Optional: Guide them to /start
        # await update.message.reply_text("Please use /start to begin.")
        return

    user_data = user_doc.to_dict()
    state = user_data.get("state")

    # --- State-Based Conversations (PRIORITY 1) ---
    # These override reply button checks if the user is in a specific flow.

    if state == "in_onboarding":
        onboarding_step = user_data.get("onboarding_step")
        user_input = text

        if onboarding_step == "real_name":
            user_ref.update({"real_name": user_input, "onboarding_step": "player_name"})
            await update.message.reply_text("\u2705 Real Name Recorded.\n\nNow, enter your desired **Player Name**.") # Check Mark ✅
        elif onboarding_step == "player_name":
            user_ref.update({"player_name": user_input, "username": user_input.lower(), "onboarding_step": "dob"})
            await update.message.reply_text("\u2705 Player Name Set.\n\nNext, provide your **Date of Birth** (DD/MM/YYYY).")
        elif onboarding_step == "dob":
            try:
                datetime.strptime(user_input, '%d/%m/%Y')
                user_ref.update({"dob": user_input, "onboarding_step": "weight"})
                await update.message.reply_text("\u2705 Date of Birth Recorded.\n\nNow, enter your current **Weight** (e.g., 75 kg).")
            except ValueError:
                await update.message.reply_text("\u274c Invalid date format. Please use DD/MM/YYYY.") # Cross Mark ❌
        elif onboarding_step == "weight":
            user_ref.update({"weight": user_input, "onboarding_step": "aim"})
            aim_options = [ # Use escapes
                "\u2694\ufe0f Awaken Physical Power (STR/STA)", "\u26a1\ufe0f Optimize Energy Reserves (Weight Loss)",
                "\U0001f9e0 Enhance Mental Fortitude (Focus)", "\U0001f4da Acquire New 'Class' Skills (Learning)",
                "\U0001f3c6 Ascend the Ranks (Overall Growth)"
            ]
            keyboard = [[InlineKeyboardButton(option, callback_data=f"aim_{i}")] for i, option in enumerate(aim_options)]
            await update.message.reply_text(
                "\u2705 Weight Recorded.\n\nFinally, declare your **Primary Objective**:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        # Aim selection is handled by button_handler
        return # Onboarding step handled

    elif state == "awaiting_code":
        # --- Activation Code Logic ---
        input_code = text.strip().upper() # Clean input
        processing_msg = await update.message.reply_text(f"\U0001f512 Verifying Access Code: {input_code}...") # Lock 🔒
        await asyncio.sleep(1.0)
        
        code_ref = db.collection("activation_codes").document(input_code)
        code_doc = code_ref.get()

        if not code_doc.exists:
            await processing_msg.edit_text("\u274c Invalid Code Signature.") # Cross Mark ❌
            return # Keep state

        code_data = code_doc.to_dict()

        # Check if already used
        if code_data.get("used_by"):
            await processing_msg.edit_text("\U0001f6ab Code Already Bound to another Hunter.") # Prohibited 🚫
            user_ref.update({"state": firestore.DELETE_FIELD})
            return

        await processing_msg.edit_text("\U0001f511 Code Signature Valid. Accessing Archives...") # Key 🔑
        await asyncio.sleep(1.0)

        # --- CALCULATE NEW EXPIRY (THE FIX) ---
        duration_days = code_data.get("duration_days", 0)
        
        # Fallback for old legacy codes that might have 'expires_at' instead of duration
        if duration_days == 0 and code_data.get("expires_at"):
             # Legacy logic (not ideal, but prevents crash)
             new_expiry_date = code_data.get("expires_at")
             if new_expiry_date.tzinfo is None: new_expiry_date = new_expiry_date.replace(tzinfo=timezone.utc)
        else:
             # NEW LOGIC: Calculate based on NOW + DURATION
             now = datetime.now(timezone.utc)
             current_user_expiry = user_data.get("expires_at")
             
             # Ensure current expiry is timezone aware if it exists
             if isinstance(current_user_expiry, datetime) and current_user_expiry.tzinfo is None:
                 current_user_expiry = current_user_expiry.replace(tzinfo=timezone.utc)

             # Stacking Logic:
             # If user is still active, ADD time to their current expiry.
             # If user is expired or new, start time from NOW.
             if isinstance(current_user_expiry, datetime) and current_user_expiry > now:
                 new_expiry_date = current_user_expiry + timedelta(days=duration_days)
             else:
                 new_expiry_date = now + timedelta(days=duration_days)

        # --- UPDATE DATABASE ---
        username = user_data.get("player_name", update.effective_user.username or f"User_{user_id}").lower()
        is_returning_user = user_data.get("level") is not None

        # Mark code as used
        code_ref.update({
            "used_by": user_id, 
            "activated_by_username": username,
            "activated_at": firestore.SERVER_TIMESTAMP
        })

        if is_returning_user:
            await processing_msg.edit_text("\U0001f504 Renewing Contract...") # Refresh 🔄
            await asyncio.sleep(1.0)
            
            user_ref.update({
                "expires_at": new_expiry_date,
                "state": firestore.DELETE_FIELD # Clear state
            })
            
            days_left = (new_expiry_date - datetime.now(timezone.utc)).days
            renewal_message = (
                f"**CONTRACT RENEWED // ACCESS EXTENDED**\n\n"
                f"Welcome back, Hunter @{username}.\n\n"
                f"Access extended. Contract valid for `{days_left}` days.\n"
                f"Continue your grind. Use the interface below."
            )
            await processing_msg.edit_text(renewal_message, parse_mode=ParseMode.MARKDOWN)
            
            # Send the main reply keyboard
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚙️ **System Interface Restored.**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_REPLY_MARKUP
            )

        else: # New User
            user_ref.set({
                "real_name": user_data.get("real_name", "N/A"), 
                "player_name": user_data.get("player_name", username),
                "dob": user_data.get("dob", "N/A"), 
                "weight_initial": user_data.get("weight", "N/A"),
                "primary_aim": user_data.get("primary_aim", "N/A"), 
                "username": username,
                "package": "Abyss Protocol", 
                "activated_at": firestore.SERVER_TIMESTAMP,
                "expires_at": new_expiry_date, # Use the calculated date
                "xp": 0, "level": 1, "rank": "E",
                "inventory": {}, "perks": [], "current_mission": None,
                "state": firestore.DELETE_FIELD, 
                "has_accepted_honor_code": False
            }, merge=True)

            welcome_caption = (f"**SYSTEM ONLINE // CONTRACT SEALED**\n\n"
                               f"Welcome, Hunter @{username}.\n\n"
                               f"Acknowledge the code...")
            
            try:
                # 1. Delete the "Processing..." message first
                await processing_msg.delete()

                # 2. Send Welcome Photo (Markdown is okay here)
                await update.message.reply_photo(
                    photo=BG_WELCOME_FILE_ID, 
                    caption=welcome_caption, 
                    parse_mode=ParseMode.MARKDOWN
                )

                # 3. Send Honor Code (MUST BE HTML TO FIX THE ERROR)
                await update.message.reply_text(
                    text=HONOR_CODE_TEXT, 
                    reply_markup=HONOR_KEYBOARD, 
                    parse_mode=ParseMode.HTML  # <--- CHANGED THIS
                )

            except Exception as e:
                print(f"Error sending welcome assets: {e}")
                # Fallback: Send plain text using HTML if photo fails
                await update.message.reply_text(
                    text=f"<b>WELCOME, {username}.</b>\n\n{HONOR_CODE_TEXT}", 
                    reply_markup=HONOR_KEYBOARD,
                    parse_mode=ParseMode.HTML # <--- CHANGED THIS
                )
        
        return # Activation handled
        
    elif state == "awaiting_guild_name":
        guild_name = text.replace(".", "").replace("/", "")
        if not (3 <= len(guild_name) <= 25):
            await update.message.reply_text("\u274c Guild name must be 3-25 characters.") # Cross Mark ❌
            return
        context.user_data['guild_name_temp'] = guild_name
        user_ref.update({"state": "awaiting_guild_tag"})
        await update.message.reply_text(f"Name set to **{guild_name}**.\nNow, provide a **Guild Tag** (3-5 characters).", parse_mode=ParseMode.MARKDOWN)
        return

    elif state == "awaiting_guild_tag":
        guild_name = context.user_data.get('guild_name_temp')
        guild_tag = text.upper()
        if not guild_name:
            await update.message.reply_text("Error: Context lost. Use /guild_create again.")
            user_ref.update({"state": firestore.DELETE_FIELD})
            return
        if not (3 <= len(guild_tag) <= 5):
            await update.message.reply_text("\u274c Tag must be 3-5 characters.")
            return

        guilds_ref = db.collection("guilds")
        # --- Check for existing name/tag (Combine checks for efficiency) ---
        name_check_query = guilds_ref.where(filter=FieldFilter("name_lower", "==", guild_name.lower())).limit(1).stream()
        tag_check_query = guilds_ref.where(filter=FieldFilter("tag", "==", guild_tag)).limit(1).stream()
        if next(name_check_query, None):
            await update.message.reply_text(f"\u274c Guild name '{guild_name}' already exists.")
            user_ref.update({"state": firestore.DELETE_FIELD})
            if 'guild_name_temp' in context.user_data: del context.user_data['guild_name_temp']
            return
        if next(tag_check_query, None):
            await update.message.reply_text(f"\u274c Guild tag '{guild_tag}' already exists.")
            user_ref.update({"state": firestore.DELETE_FIELD})
            if 'guild_name_temp' in context.user_data: del context.user_data['guild_name_temp']
            return
        # --- End Checks ---

        # Create guild (using fields from previous steps)
        new_guild_ref = guilds_ref.document()
        initial_xp_to_next = int(GUILD_XP_PER_LEVEL_BASE)
        new_guild_ref.set({
             "id": new_guild_ref.id, "name": guild_name, "name_lower": guild_name.lower(),
             "tag": guild_tag, "leader_id": user_id, "leader_name": user_data.get("username", "Unknown"),
             "created_at": firestore.SERVER_TIMESTAMP, "member_count": 1,
             "members": {user_id: "Leader"}, "level": 1, "xp": 0,
             "xp_to_next_level": initial_xp_to_next, "active_perks": [], "perk_effects": [],
             "treasury": {}, "active_mission": None
        })
        user_ref.update({
             "guild_id": new_guild_ref.id, "guild_role": "Leader",
             "state": firestore.DELETE_FIELD
        })
        if 'guild_name_temp' in context.user_data: del context.user_data['guild_name_temp']
        # Show reply keyboard after successful guild creation
        await update.message.reply_text(f"\u2705 **Guild Founded!** Welcome to **{guild_name} [{guild_tag}]**.", parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_REPLY_MARKUP)
        return

    elif state == "awaiting_sell_info":
        await handle_sell_info(update, context) # Assumes this handles its own reply/state
        return

    elif state == "awaiting_donation_info":
        await handle_donation_info(update, context) # Assumes this handles its own reply/state
        return

    elif state == "awaiting_photo_proof":
         await update.message.reply_text("\u274c Photo proof required. Please send an image.") # Cross Mark ❌
         return # Keep state

    # --- Reply Keyboard Button Handling (PRIORITY 2) ---
    # Only run if not currently in a specific state handled above.
    button_command_map = {
        # Map Button Text -> Command Function
        "\U0001f4dc Mission": mission,              # Scroll 📜
        "\U0001f464 Profile": profile,              # Bust in Silhouette 👤
        "\U0001f9f3 Inventory": inventory,          # Backpack 🎒
        "\U0001f3ad Black Market": blackmarket,      # Mask 🎭
        "\U0001f6e1\ufe0f Guild Hall": guild_hall,  # Shield 🛡️
        "\U0001f47b Regiment": regiment,            # Ghost 👻
        "\U0001f513 Activate": activate,            # Lock 🔓 (Open Lock, actually)
        "\u2753 Explain Cmds": explain_command_handler # Question Mark ❓
    }

    command_function = button_command_map.get(text)
    if command_function:
        # Check if user data exists (might not if they used /start but didn't finish onboarding)
        if not user_data:
             await update.message.reply_text("Please complete onboarding first using /start.")
             return

        # Manually run pre-command checks (status, ban, expiry)
        # Note: We use user_data fetched at the start of the handler
        if "level" not in user_data: # Not activated
            await update.message.reply_text("\u26a0\ufe0f Activation required. Use /start or the 'Activate' button.") # Warning ⚠️
            return
        if user_data.get("is_banned", False): # Banned
            await update.message.reply_text("**ACCOUNT LOCKED**")
            return
        expires_at_check = user_data.get("expires_at", datetime(1970, 1, 1, tzinfo=timezone.utc)) # Expired
        if not isinstance(expires_at_check, datetime): expires_at_check = datetime(1970, 1, 1, tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at_check:
            await update.message.reply_text("\u26d3\ufe0f Contract Expired. Use the 'Activate' button.") # Chains ⛓️
            return

        # --- Execute the command function ---
        try:
            await command_function(update, context)
        except Exception as e:
            print(f"Error running command '{text}' via reply button: {e}")
            await update.message.reply_text(f"\u26a0\ufe0f Error executing command: {text}") # Warning ⚠️
        return # Handled button press

    # --- Fallback (PRIORITY 3) ---
    # If the text wasn't handled by a state and wasn't a reply button text:
    # Optional: Send a generic message or ignore.
    # Check if user is activated before sending fallback to avoid spamming onboarding users
    # if user_data.get("level"):
    #    await update.message.reply_text("Unknown input. Use the buttons below or /help.", reply_markup=MAIN_REPLY_MARKUP)





# REPLACE your old get_file_id function with this one.
@admin_only
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A helper command to get the file_id of any replied-to media."""
    replied_message = update.message.reply_to_message
    if not replied_message:
        await update.message.reply_text("Please reply to a message with media.")
        return

    file_id = None
    if replied_message.photo:
        file_id = replied_message.photo[-1].file_id
        media_type = "Photo"
    elif replied_message.voice:
        file_id = replied_message.voice.file_id
        media_type = "Voice Note"
    elif replied_message.audio:
        file_id = replied_message.audio.file_id
        media_type = "Audio"
    elif replied_message.video:
        file_id = replied_message.video.file_id
        media_type = "Video"
    elif replied_message.animation:
        file_id = replied_message.animation.file_id
        media_type = "Animation (GIF)"
    
    if file_id:
        await update.message.reply_text(f"**{media_type} Detected**\n\nFile ID: `{file_id}`", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Could not find a file ID in the replied message.")

# In your main block, make sure the handler points to the new function name
# app.add_handler(CommandHandler("getid", get_id))


# --- MAIN EXECUTION BLOCK ---

# --- (NEW async main block) ---
async def main():
    """Starts the bot."""
    # Set a 60-second timeout for all network operations
    request_settings = HTTPXRequest(connection_pool_size=8, read_timeout=60, write_timeout=60, connect_timeout=60)
    app = ApplicationBuilder().token(bot_token).request(request_settings).build()

    # --- Add Handlers ---
    # Core commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("activate", activate))
    app.add_handler(CommandHandler("mission", mission))
    app.add_handler(CommandHandler("complete", complete))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("inventory", inventory))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("set_next_mission", set_next_mission))

    # Economy commands
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("what", what))
    app.add_handler(CommandHandler("blackmarket", blackmarket))
    app.add_handler(CommandHandler("finalize_sale", finalize_sale))
    app.add_handler(CommandHandler("cancel_sale", cancel_sale))
    

    # Shadow Regiment commands
    app.add_handler(CommandHandler("regiment", regiment))
    
    # Guild commands
    app.add_handler(CommandHandler("guild", guild))
    app.add_handler(CommandHandler("guild_create", guild_create))
    app.add_handler(CommandHandler("guild_invite", guild_invite))
    app.add_handler(CommandHandler("guild_leave", guild_leave))
    app.add_handler(CommandHandler("guild_promote", guild_promote))
    app.add_handler(CommandHandler("guild_kick", guild_kick))
    app.add_handler(CommandHandler("guild_rename", guild_rename))
    app.add_handler(CommandHandler("guild_members", guild_members))
    app.add_handler(CommandHandler("guild_disband", guild_disband))
    app.add_handler(CommandHandler("guild_hall", guild_hall))
    app.add_handler(CommandHandler("guild_treasury", guild_treasury))
    app.add_handler(CommandHandler("guild_donate", guild_donate))
    app.add_handler(CommandHandler("force_reset_guild_mission", force_reset_guild_mission))
    app.add_handler(CommandHandler("create_rival_guild", create_rival_guild))
    app.add_handler(CommandHandler("control_guild", control_guild))
    # Add guild_mission handler here later

    # World Boss commands
    app.add_handler(CommandHandler("worldboss", worldboss))
    app.add_handler(CommandHandler("set_active_boss", set_active_boss))
    app.add_handler(CommandHandler("worldboss_damage", worldboss_damage))
    app.add_handler(CommandHandler("generate_code", generate_code))
    
    # Admin commands
    app.add_handler(CommandHandler("getid", get_id)) # Your existing getid
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("view_user", view_user))
    app.add_handler(CommandHandler("give_item", give_item))
    app.add_handler(CommandHandler("extend_sub", extend_sub))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("ban_user", ban_user))
    app.add_handler(CommandHandler("unban_user", unban_user))
    app.add_handler(CommandHandler("set_level", set_level))
    app.add_handler(CommandHandler("set_xp", set_xp))
    app.add_handler(CommandHandler("take_item", take_item))
    app.add_handler(CommandHandler("system", system_menu))
    app.add_handler(CommandHandler("guild_mission", guild_mission)) 
    app.add_handler(CommandHandler("guild_mission_start", guild_mission_start))
    app.add_handler(CommandHandler("create_npc", create_npc))
    app.add_handler(CommandHandler("npc_action", npc_action))
    app.add_handler(CommandHandler("deal_damage", admin_deal_damage))
    app.add_handler(CommandHandler("fake_damage", add_fake_damage))
    app.add_handler(CommandHandler("player_audit", player_audit))
    app.add_handler(CommandHandler("set_badge", set_badge))

    # Message and Callback Handlers
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_proof))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_text_handler))
    app.add_handler(CommandHandler("explain", explain_command_handler))
    app.add_handler(CommandHandler("use", use_item))
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("equip", equip))
    app.add_handler(CommandHandler("unequip", unequip))
    app.add_handler(CommandHandler("loadout", loadout))
    app.add_handler(CommandHandler("guild_promote_officer", guild_promote_officer))
    app.add_handler(CommandHandler("guild_demote_officer", guild_demote_officer))
    app.add_handler(CommandHandler("top_guilds", leaderboard_guilds))
    app.add_handler(CommandHandler("leaderboard_guilds", leaderboard_guilds))
    

    # --- Initialize the application ---
    print("Initializing Application...")
    await app.initialize() # <--- THIS IS THE IMPORTANT ADDITION

    print(f"🤖 ShadowGrind System [v1.5] is live at {datetime.now()}. Starting polling...")
    
    # --- Start polling ---
    # We don't need run_polling() anymore when using async main
    await app.updater.start_polling() 
    await app.start()
    
    # Keep the bot running until interrupted
    while True:
        await asyncio.sleep(3600) # Sleep for an hour, or adjust as needed

if __name__ == "__main__":
    keep_alive() # Starts the web server for Render

    asyncio.run(main())





































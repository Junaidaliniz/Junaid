import asyncio
import requests
import re
import phonenumbers
from phonenumbers import geocoder
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import json
import os

# ============================================
# CONFIGURATION - CHANGE THESE VALUES
# ============================================
BOT_TOKEN = "8446798065:AAEDTwui0WLYpk1HocouDDjw4xhJVoIQncA"
DEFAULT_OWNERS = [7011937754]
# ============================================

bot = Bot(token=BOT_TOKEN)

DATA_DIR = "data"
PANELS_FILE = os.path.join(DATA_DIR, "panels.json")
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")
OWNERS_FILE = os.path.join(DATA_DIR, "owners.json")
OTP_FILE = os.path.join(DATA_DIR, "otp_store.json")
SEEN_FILE = os.path.join(DATA_DIR, "seen.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ============================
# JSON HELPERS
# ============================
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f, indent=2)
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ============================
# LOAD DATA
# ============================
panels = load_json(PANELS_FILE, {})
# groups = {"group_id": {"active": true, "panel": "all", "buttons": [{"name": "...", "url": "..."}]}}
groups = load_json(GROUPS_FILE, {})
owners = load_json(OWNERS_FILE, DEFAULT_OWNERS)
otp_store = load_json(OTP_FILE, {})
seen_messages = load_json(SEEN_FILE, {})

# Default buttons for new groups
DEFAULT_BUTTONS = [
    {"name": "🟢 Whatsapp", "url": "https://whatsapp.com/channel/0029Vaf1X3f6hENsP7dKm81z"},
    {"name": "💻 Developer", "url": "https://t.me/junaidniz786"},
    {"name": "📱 Channel", "url": "https://t.me/jndtech1"},
    {"name": "☎️ Number", "url": "https://t.me/+c4VCxBCT3-QzZGFk"}
]

# Welcome message config
WELCOME_FILE = os.path.join(DATA_DIR, "welcome.json")
DEFAULT_WELCOME = {
    "message": "👋 Welcome! This bot forwards OTP messages in real-time.\n\nClick the button below to join the group where OTPs are posted:",
    "buttons": [
        {"name": "🏛 Available Numbers", "url": "https://t.me/jndtech1"},
        {"name": "💬 Main Chat", "url": "https://t.me/junaidniz786"},
        {"name": "🔑 Otp Group", "url": "https://t.me/+c4VCxBCT3-QzZGFk"}
    ]
}
welcome_config = load_json(WELCOME_FILE, DEFAULT_WELCOME)

# ============================
# CONVERSATION STATES
# ============================
STATE_ADD_PANEL_NAME = 1
STATE_ADD_PANEL_URL = 2
STATE_ADD_PANEL_TOKEN = 3
STATE_ADD_PANEL_RECORDS = 4
STATE_ADD_GROUP = 5
STATE_ADD_OWNER = 6
STATE_ASSIGN_PANEL_GROUP = 7
STATE_ADD_BUTTON_NAME = 8
STATE_ADD_BUTTON_URL = 9
STATE_EDIT_WELCOME_MSG = 10
STATE_ADD_WELCOME_BTN_NAME = 11
STATE_ADD_WELCOME_BTN_URL = 12

# ============================
# FETCH FUNCTIONS
# ============================
def fetch_latest(panel_name):
    if panel_name not in panels:
        return None
    cfg = panels[panel_name]
    if not cfg.get("active", True):
        return None
    try:
        response = requests.get(cfg["url"], params={
            "token": cfg["token"],
            "records": cfg.get("records", 20)
        }, timeout=10)
        data = response.json()
        if data.get("status") != "success":
            print(f"{panel_name.upper()} API Error:", data)
            return None
        records = data.get("data", [])
        if not records:
            return None
        latest = records[0]
        return {
            "time": latest.get("dt", ""),
            "number": latest.get("num", ""),
            "service": latest.get("cli", ""),
            "message": latest.get("message", ""),
            "panel": panel_name
        }
    except Exception as e:
        print(f"{panel_name.upper()} Fetch Error:", e)
        return None

# ============================
# HELPERS
# ============================
def extract_otp(message):
    for pat in [r'\d{6}', r'\d{4}', r'\d{3}-\d{3}']:
        match = re.search(pat, message)
        if match:
            return match.group(0)
    return "N/A"

def mask_number(number_str):
    try:
        if not number_str.startswith("+"):
            number_str = f"+{number_str}"
        length = len(number_str)
        show_first = 5 if length >= 10 else 4
        show_last = 4 if length >= 10 else 2
        stars = "*" * (length - show_first - show_last)
        return f"{number_str[:show_first]}{stars}{number_str[-show_last:]}"
    except:
        return f"+{number_str}"

def get_country_info(number_str):
    try:
        if not number_str.startswith("+"):
            number_str = "+" + number_str
        parsed = phonenumbers.parse(number_str)
        country_name = geocoder.description_for_number(parsed, "en")
        region = phonenumbers.region_code_for_number(parsed)
        if region and len(region) == 2:
            base = 127462 - ord("A")
            flag = chr(base + ord(region[0])) + chr(base + ord(region[1]))
        else:
            flag = "🌍"
        return country_name or "Unknown", flag
    except:
        return "Unknown", "🌍"

# ============================
# MESSAGE FORMATTING
# ============================
def format_message(record):
    raw = record["message"]
    otp = extract_otp(raw)
    clean = raw.replace("<", "&lt;").replace(">", "&gt;")
    country, flag = get_country_info(record["number"])
    masked = mask_number(record["number"])
    panel_name = record.get("panel", "Panel")
    border = "═" * 35

    return f"""
🟢 <b>✨🛡 {panel_name.upper()} OTP ALERT 🛡✨</b> 🟢
<code>{border}</code>
<b>Service:</b> {record['service']} 📊
<b>Number:</b> {masked} 🔢
<b>Country:</b> {flag} {country}
<b>Time:</b> 🕒 {record['time']}
<b>OTP:</b> <code>{otp}</code> 💠
<b>Full Message:</b> 📝
<pre>{clean}</pre>
<code>{border}</code>
⚡️ Powered by <b>Junaid Niz</b> ⚡️
"""

def get_keyboard_for_group(gid):
    """Build dynamic keyboard from group's button list"""
    cfg = groups.get(gid, {})
    btns = cfg.get("buttons", DEFAULT_BUTTONS)
    kb = []
    row = []
    for btn in btns:
        row.append(InlineKeyboardButton(btn["name"], url=btn["url"]))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(kb) if kb else None

# ============================
# SEND TO GROUPS
# ============================
async def send_to_groups(msg, panel_name):
    for gid, cfg in groups.items():
        if not cfg.get("active", True):
            continue
        assigned_panel = cfg.get("panel", "all")
        if assigned_panel != "all" and assigned_panel != panel_name:
            continue
        try:
            keyboard = get_keyboard_for_group(gid)
            await bot.send_message(chat_id=int(gid), text=msg, parse_mode="HTML", reply_markup=keyboard)
            print(f"[SENT] {panel_name} -> {gid}")
        except Exception as e:
            print(f"Send Error -> {gid}: {e}")

# ============================
# MENU KEYBOARDS
# ============================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Panel List", callback_data="panel_list")],
        [InlineKeyboardButton("📂 Group List", callback_data="group_list")],
        [InlineKeyboardButton("🔧 Owner Panel", callback_data="owner_panel")],
    ])

def owner_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Panel", callback_data="add_panel")],
        [InlineKeyboardButton("➕ Add Group", callback_data="add_group")],
        [InlineKeyboardButton("➕ Add Owner", callback_data="add_owner")],
        [InlineKeyboardButton("📋 Assign Panel to Group", callback_data="assign_panel")],
        [InlineKeyboardButton("👋 Welcome Settings", callback_data="welcome_settings")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

def welcome_settings_keyboard():
    btn_count = len(welcome_config.get("buttons", []))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Message", callback_data="welcome_edit_msg")],
        [InlineKeyboardButton(f"🔘 Buttons ({btn_count})", callback_data="welcome_buttons")],
        [InlineKeyboardButton("⬅️ Back", callback_data="owner_panel")],
    ])

def welcome_buttons_keyboard():
    btns = welcome_config.get("buttons", [])
    kb = []
    for i, btn in enumerate(btns):
        kb.append([InlineKeyboardButton(f"🔘 {btn['name']}", callback_data=f"wbtn_details|{i}")])
    if not kb:
        kb.append([InlineKeyboardButton("No buttons", callback_data="noop")])
    kb.append([InlineKeyboardButton("➕ Add Button", callback_data="wbtn_add")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="welcome_settings")])
    return InlineKeyboardMarkup(kb)

def welcome_btn_details_keyboard(idx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete", callback_data=f"wbtn_delete|{idx}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="welcome_buttons")],
    ])

def panel_list_keyboard():
    kb = []
    for name, cfg in panels.items():
        status = "🟢" if cfg.get("active", True) else "🔴"
        kb.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"panel_details|{name}")])
    if not kb:
        kb.append([InlineKeyboardButton("No panels added", callback_data="noop")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(kb)

def panel_details_keyboard(name):
    cfg = panels.get(name, {})
    active = cfg.get("active", True)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'🔴 Deactivate' if active else '🟢 Activate'}", callback_data=f"panel_toggle|{name}")],
        [InlineKeyboardButton("🗑 Delete", callback_data=f"panel_delete|{name}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="panel_list")],
    ])

def group_list_keyboard():
    kb = []
    for gid, cfg in groups.items():
        status = "🟢" if cfg.get("active", True) else "🔴"
        panel = cfg.get("panel", "all")
        kb.append([InlineKeyboardButton(f"{status} {gid} [{panel}]", callback_data=f"group_details|{gid}")])
    if not kb:
        kb.append([InlineKeyboardButton("No groups added", callback_data="noop")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(kb)

def group_details_keyboard(gid):
    cfg = groups.get(gid, {})
    active = cfg.get("active", True)
    btn_count = len(cfg.get("buttons", DEFAULT_BUTTONS))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'🔴 Deactivate' if active else '🟢 Activate'}", callback_data=f"group_toggle|{gid}")],
        [InlineKeyboardButton(f"🔘 Buttons ({btn_count})", callback_data=f"group_buttons|{gid}")],
        [InlineKeyboardButton("📋 Change Panel", callback_data=f"group_change_panel|{gid}")],
        [InlineKeyboardButton("🗑 Delete", callback_data=f"group_delete|{gid}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="group_list")],
    ])

def select_panel_keyboard(gid):
    kb = [[InlineKeyboardButton("📋 All Panels", callback_data=f"set_group_panel|{gid}|all")]]
    for name in panels:
        kb.append([InlineKeyboardButton(name, callback_data=f"set_group_panel|{gid}|{name}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data=f"group_details|{gid}")])
    return InlineKeyboardMarkup(kb)

def group_buttons_keyboard(gid):
    cfg = groups.get(gid, {})
    btns = cfg.get("buttons", DEFAULT_BUTTONS)
    kb = []
    for i, btn in enumerate(btns):
        kb.append([InlineKeyboardButton(f"🔘 {btn['name']}", callback_data=f"btn_details|{gid}|{i}")])
    if not kb:
        kb.append([InlineKeyboardButton("No buttons", callback_data="noop")])
    kb.append([InlineKeyboardButton("➕ Add Button", callback_data=f"btn_add|{gid}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data=f"group_details|{gid}")])
    return InlineKeyboardMarkup(kb)

def button_details_keyboard(gid, idx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete", callback_data=f"btn_delete|{gid}|{idx}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"group_buttons|{gid}")],
    ])

# ============================
# WELCOME KEYBOARD FOR NORMAL USERS
# ============================
def get_welcome_keyboard():
    btns = welcome_config.get("buttons", [])
    kb = []
    row = []
    for btn in btns:
        row.append(InlineKeyboardButton(btn["name"], url=btn["url"]))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(kb) if kb else None

# ============================
# COMMAND HANDLERS
# ============================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in owners:
        await update.message.reply_text("👑 Owner Panel — choose an action:", reply_markup=main_keyboard())
    else:
        msg = welcome_config.get("message", "Welcome!")
        await update.message.reply_text(msg, reply_markup=get_welcome_keyboard())

async def id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: `{update.effective_chat.id}`", parse_mode="Markdown")

# ============================
# CALLBACK HANDLER
# ============================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global panels, groups, owners
    
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    data = query.data
    user = query.from_user

    context.user_data.pop("state", None)

    if data == "noop":
        return

    if data == "back_main":
        await query.edit_message_text("Welcome — choose an action:", reply_markup=main_keyboard())
        return

    if data == "panel_list":
        await query.edit_message_text("📋 All Panels:", reply_markup=panel_list_keyboard())
        return

    if data == "group_list":
        await query.edit_message_text("📂 All Groups:", reply_markup=group_list_keyboard())
        return

    if data == "owner_panel":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        await query.edit_message_text("🔧 Owner Panel:", reply_markup=owner_keyboard())
        return

    if data == "add_panel":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        context.user_data["state"] = STATE_ADD_PANEL_NAME
        await query.edit_message_text("<b>➕ Add Panel</b>\n\nStep 1/4: Send <b>Panel Name</b>:", parse_mode="HTML")
        return

    if data == "add_group":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        context.user_data["state"] = STATE_ADD_GROUP
        await query.edit_message_text("<b>➕ Add Group</b>\n\nSend <b>Group ID</b> (e.g., -1001234567890):", parse_mode="HTML")
        return

    if data == "add_owner":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        context.user_data["state"] = STATE_ADD_OWNER
        await query.edit_message_text("<b>➕ Add Owner</b>\n\nSend <b>User ID</b>:", parse_mode="HTML")
        return

    if data == "assign_panel":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        context.user_data["state"] = STATE_ASSIGN_PANEL_GROUP
        await query.edit_message_text("<b>📋 Assign Panel</b>\n\nSend <b>Group ID</b>:", parse_mode="HTML")
        return

    if data.startswith("panel_details|"):
        name = data.split("|")[1]
        cfg = panels.get(name, {})
        status = "🟢 Active" if cfg.get("active", True) else "🔴 Inactive"
        text = f"<b>📋 {name}</b>\n\nURL: <code>{cfg.get('url', 'N/A')}</code>\nToken: <code>{cfg.get('token', 'N/A')}</code>\nRecords: {cfg.get('records', 20)}\nStatus: {status}"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=panel_details_keyboard(name))
        return

    if data.startswith("panel_toggle|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        name = data.split("|")[1]
        if name in panels:
            panels[name]["active"] = not panels[name].get("active", True)
            save_json(PANELS_FILE, panels)
        await query.edit_message_text("Panel updated!", reply_markup=panel_list_keyboard())
        return

    if data.startswith("panel_delete|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        name = data.split("|")[1]
        if name in panels:
            del panels[name]
            save_json(PANELS_FILE, panels)
        await query.edit_message_text("Panel deleted!", reply_markup=panel_list_keyboard())
        return

    if data.startswith("group_details|"):
        gid = data.split("|")[1]
        cfg = groups.get(gid, {})
        status = "🟢 Active" if cfg.get("active", True) else "🔴 Inactive"
        panel = cfg.get("panel", "all")
        btn_count = len(cfg.get("buttons", DEFAULT_BUTTONS))
        text = f"<b>📂 Group: {gid}</b>\n\nStatus: {status}\nAssigned Panel: <b>{panel}</b>\nButtons: {btn_count}"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=group_details_keyboard(gid))
        return

    if data.startswith("group_toggle|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        gid = data.split("|")[1]
        if gid in groups:
            groups[gid]["active"] = not groups[gid].get("active", True)
            save_json(GROUPS_FILE, groups)
        await query.edit_message_text("Group updated!", reply_markup=group_list_keyboard())
        return

    if data.startswith("group_delete|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        gid = data.split("|")[1]
        if gid in groups:
            del groups[gid]
            save_json(GROUPS_FILE, groups)
        await query.edit_message_text("Group deleted!", reply_markup=group_list_keyboard())
        return

    if data.startswith("group_change_panel|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        gid = data.split("|")[1]
        await query.edit_message_text(f"Select Panel for Group {gid}:", reply_markup=select_panel_keyboard(gid))
        return

    if data.startswith("set_group_panel|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        parts = data.split("|")
        gid = parts[1]
        panel_name = parts[2]
        if gid in groups:
            groups[gid]["panel"] = panel_name
            save_json(GROUPS_FILE, groups)
        await query.edit_message_text(f"Group {gid} assigned to <b>{panel_name}</b>", parse_mode="HTML", reply_markup=group_list_keyboard())
        return

    # GROUP BUTTONS
    if data.startswith("group_buttons|"):
        gid = data.split("|")[1]
        await query.edit_message_text(f"🔘 Buttons for Group {gid}:", reply_markup=group_buttons_keyboard(gid))
        return

    if data.startswith("btn_details|"):
        parts = data.split("|")
        gid = parts[1]
        idx = int(parts[2])
        cfg = groups.get(gid, {})
        btns = cfg.get("buttons", DEFAULT_BUTTONS)
        if idx < len(btns):
            btn = btns[idx]
            text = f"<b>🔘 Button Details</b>\n\nName: {btn['name']}\nURL: {btn['url']}"
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=button_details_keyboard(gid, idx))
        return

    if data.startswith("btn_delete|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        parts = data.split("|")
        gid = parts[1]
        idx = int(parts[2])
        if gid in groups:
            btns = groups[gid].get("buttons", DEFAULT_BUTTONS.copy())
            if idx < len(btns):
                del btns[idx]
                groups[gid]["buttons"] = btns
                save_json(GROUPS_FILE, groups)
        await query.edit_message_text("Button deleted!", reply_markup=group_buttons_keyboard(gid))
        return

    if data.startswith("btn_add|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        gid = data.split("|")[1]
        context.user_data["state"] = STATE_ADD_BUTTON_NAME
        context.user_data["btn_group"] = gid
        await query.edit_message_text(f"<b>➕ Add Button to Group {gid}</b>\n\nStep 1/2: Send <b>Button Name</b> (e.g., 📱 Channel):", parse_mode="HTML")
        return

    # WELCOME SETTINGS
    if data == "welcome_settings":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        msg = welcome_config.get("message", "No message set")
        text = f"<b>👋 Welcome Settings</b>\n\n<b>Current Message:</b>\n{msg}"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=welcome_settings_keyboard())
        return

    if data == "welcome_edit_msg":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        context.user_data["state"] = STATE_EDIT_WELCOME_MSG
        await query.edit_message_text("<b>✏️ Edit Welcome Message</b>\n\nSend new welcome message:", parse_mode="HTML")
        return

    if data == "welcome_buttons":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        await query.edit_message_text("🔘 Welcome Buttons:", reply_markup=welcome_buttons_keyboard())
        return

    if data.startswith("wbtn_details|"):
        idx = int(data.split("|")[1])
        btns = welcome_config.get("buttons", [])
        if idx < len(btns):
            btn = btns[idx]
            text = f"<b>🔘 Button Details</b>\n\nName: {btn['name']}\nURL: {btn['url']}"
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=welcome_btn_details_keyboard(idx))
        return

    if data.startswith("wbtn_delete|"):
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        idx = int(data.split("|")[1])
        btns = welcome_config.get("buttons", [])
        if idx < len(btns):
            del btns[idx]
            welcome_config["buttons"] = btns
            save_json(WELCOME_FILE, welcome_config)
        await query.edit_message_text("Button deleted!", reply_markup=welcome_buttons_keyboard())
        return

    if data == "wbtn_add":
        if user.id not in owners:
            await query.edit_message_text("Access denied.")
            return
        context.user_data["state"] = STATE_ADD_WELCOME_BTN_NAME
        await query.edit_message_text("<b>➕ Add Welcome Button</b>\n\nStep 1/2: Send <b>Button Name</b>:", parse_mode="HTML")
        return

# ============================
# MESSAGE HANDLER
# ============================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global panels, groups, owners
    
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    text = update.message.text.strip()
    state = context.user_data.get("state")
    
    if state is None:
        return

    if state == STATE_ADD_PANEL_NAME:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        context.user_data["new_panel_name"] = text
        context.user_data["state"] = STATE_ADD_PANEL_URL
        await update.message.reply_text(f"<b>Panel Name:</b> {text}\n\nStep 2/4: Send <b>Panel URL</b>:", parse_mode="HTML")
        return

    if state == STATE_ADD_PANEL_URL:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        context.user_data["new_panel_url"] = text
        context.user_data["state"] = STATE_ADD_PANEL_TOKEN
        await update.message.reply_text(f"<b>Panel URL:</b> {text}\n\nStep 3/4: Send <b>Panel Token</b>:", parse_mode="HTML")
        return

    if state == STATE_ADD_PANEL_TOKEN:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        context.user_data["new_panel_token"] = text
        context.user_data["state"] = STATE_ADD_PANEL_RECORDS
        await update.message.reply_text(f"<b>Panel Token:</b> {text}\n\nStep 4/4: Send <b>Records Count</b> (e.g., 20):", parse_mode="HTML")
        return

    if state == STATE_ADD_PANEL_RECORDS:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        try:
            records = int(text)
        except:
            records = 20
        
        name = context.user_data.get("new_panel_name", "Panel")
        url = context.user_data.get("new_panel_url", "")
        token = context.user_data.get("new_panel_token", "")
        
        panels[name] = {
            "url": url,
            "token": token,
            "records": records,
            "active": True
        }
        save_json(PANELS_FILE, panels)
        
        await update.message.reply_text(
            f"<b>✅ Panel Added!</b>\n\nName: {name}\nURL: {url}\nToken: {token}\nRecords: {records}",
            parse_mode="HTML",
            reply_markup=owner_keyboard()
        )
        
        context.user_data.pop("state", None)
        context.user_data.pop("new_panel_name", None)
        context.user_data.pop("new_panel_url", None)
        context.user_data.pop("new_panel_token", None)
        return

    if state == STATE_ADD_GROUP:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        
        gid = text.strip()
        groups[gid] = {"active": True, "panel": "all", "buttons": DEFAULT_BUTTONS.copy()}
        save_json(GROUPS_FILE, groups)
        
        await update.message.reply_text(f"<b>✅ Group Added!</b>\n\nID: {gid}\nButtons: {len(DEFAULT_BUTTONS)} (default)", parse_mode="HTML", reply_markup=owner_keyboard())
        context.user_data.pop("state", None)
        return

    if state == STATE_ADD_OWNER:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        
        try:
            new_owner = int(text)
        except:
            await update.message.reply_text("Invalid ID.")
            return
        
        if new_owner not in owners:
            owners.append(new_owner)
            save_json(OWNERS_FILE, owners)
        
        await update.message.reply_text(f"<b>✅ Owner Added!</b>\n\nID: {new_owner}", parse_mode="HTML", reply_markup=owner_keyboard())
        context.user_data.pop("state", None)
        return

    if state == STATE_ASSIGN_PANEL_GROUP:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        
        gid = text.strip()
        if gid not in groups:
            groups[gid] = {"active": True, "panel": "all", "buttons": DEFAULT_BUTTONS.copy()}
            save_json(GROUPS_FILE, groups)
        
        await update.message.reply_text(f"Select Panel for Group {gid}:", reply_markup=select_panel_keyboard(gid))
        context.user_data.pop("state", None)
        return

    if state == STATE_ADD_BUTTON_NAME:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        context.user_data["new_button_name"] = text
        context.user_data["state"] = STATE_ADD_BUTTON_URL
        await update.message.reply_text(f"<b>Button Name:</b> {text}\n\nStep 2/2: Send <b>Button URL</b>:", parse_mode="HTML")
        return

    if state == STATE_ADD_BUTTON_URL:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        
        gid = context.user_data.get("btn_group")
        name = context.user_data.get("new_button_name", "Button")
        url = text.strip()
        
        if gid and gid in groups:
            if "buttons" not in groups[gid]:
                groups[gid]["buttons"] = DEFAULT_BUTTONS.copy()
            groups[gid]["buttons"].append({"name": name, "url": url})
            save_json(GROUPS_FILE, groups)
        
        await update.message.reply_text(
            f"<b>✅ Button Added!</b>\n\nName: {name}\nURL: {url}",
            parse_mode="HTML",
            reply_markup=group_buttons_keyboard(gid)
        )
        
        context.user_data.pop("state", None)
        context.user_data.pop("new_button_name", None)
        context.user_data.pop("btn_group", None)
        return

    # WELCOME MESSAGE HANDLERS
    if state == STATE_EDIT_WELCOME_MSG:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        
        welcome_config["message"] = text
        save_json(WELCOME_FILE, welcome_config)
        
        await update.message.reply_text(
            f"<b>✅ Welcome Message Updated!</b>\n\n{text}",
            parse_mode="HTML",
            reply_markup=welcome_settings_keyboard()
        )
        context.user_data.pop("state", None)
        return

    if state == STATE_ADD_WELCOME_BTN_NAME:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        context.user_data["new_wbtn_name"] = text
        context.user_data["state"] = STATE_ADD_WELCOME_BTN_URL
        await update.message.reply_text(f"<b>Button Name:</b> {text}\n\nStep 2/2: Send <b>Button URL</b>:", parse_mode="HTML")
        return

    if state == STATE_ADD_WELCOME_BTN_URL:
        if user.id not in owners:
            await update.message.reply_text("Access denied.")
            context.user_data.pop("state", None)
            return
        
        name = context.user_data.get("new_wbtn_name", "Button")
        url = text.strip()
        
        if "buttons" not in welcome_config:
            welcome_config["buttons"] = []
        welcome_config["buttons"].append({"name": name, "url": url})
        save_json(WELCOME_FILE, welcome_config)
        
        await update.message.reply_text(
            f"<b>✅ Welcome Button Added!</b>\n\nName: {name}\nURL: {url}",
            parse_mode="HTML",
            reply_markup=welcome_buttons_keyboard()
        )
        
        context.user_data.pop("state", None)
        context.user_data.pop("new_wbtn_name", None)
        return

# ============================
# API WORKERS
# ============================
async def api_worker(panel_name):
    print(f"[STARTED] {panel_name.upper()} Worker")
    last_sig = None
    
    while True:
        if panel_name not in panels:
            await asyncio.sleep(5)
            continue
            
        data = fetch_latest(panel_name)
        if data:
            sig = data["number"] + data["message"]
            if sig != last_sig:
                last_sig = sig
                otp = extract_otp(data["message"])
                if otp and otp != "N/A":
                    otp_store[data["number"]] = otp
                    save_json(OTP_FILE, otp_store)
                
                msg = format_message(data)
                await send_to_groups(msg, panel_name)
                print(f"[{panel_name.upper()}] Sent: {data['service']} | {data['number']}")
        
        await asyncio.sleep(3)

# ============================
# WORKER MANAGER
# ============================
active_workers = {}

async def manage_workers():
    global active_workers
    while True:
        for name in list(panels.keys()):
            if name not in active_workers or active_workers[name].done():
                active_workers[name] = asyncio.create_task(api_worker(name))
                print(f"[MANAGER] Started worker for {name}")
        
        for name in list(active_workers.keys()):
            if name not in panels:
                active_workers[name].cancel()
                del active_workers[name]
                print(f"[MANAGER] Stopped worker for {name}")
        
        await asyncio.sleep(5)

# ============================
# MAIN
# ============================
def main():
    print("=" * 50)
    print("Starting Panel OTP Bot...")
    print(f"Bot Token: {BOT_TOKEN[:20]}...")
    print(f"Owners: {owners}")
    print(f"Panels: {list(panels.keys())}")
    print(f"Groups: {list(groups.keys())}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("id", id_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.create_task(manage_workers())
    
    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

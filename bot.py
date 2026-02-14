import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, NetworkError
import httpx
import time
import re
import asyncio
import logging
from datetime import datetime
import random
from database import Database

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("8535063748:AAGWG-IhlqpNaWuq1VhmWPejjzh_vUAJzGs")
OWNER_ID = int(os.environ.get("OWNER_ID", "7011937754"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

PROXY_LIST = [
    {"host": "198.105.121.200", "port": "6462", "user": "zfyocsme", "pass": "5qgnpahdg19e"},
    {"host": "64.137.96.74", "port": "6641", "user": "zfyocsme", "pass": "5qgnpahdg19e"},
    {"host": "84.247.60.125", "port": "6095", "user": "zfyocsme", "pass": "5qgnpahdg19e"},
    {"host": "23.95.150.145", "port": "6114", "user": "zfyocsme", "pass": "5qgnpahdg19e"},
    {"host": "xhmaster.shit.vc", "port": "6969", "user": "thor", "pass": "lund"},
]

def get_random_proxy():
    proxy = random.choice(PROXY_LIST)
    return proxy

def get_proxy_url(proxy=None):
    if proxy is None:
        proxy = get_random_proxy()
    return f"http://{proxy['user']}:{proxy['pass']}@{proxy['host']}:{proxy['port']}"

# Default proxy for Telegram (uses first one)
CURRENT_PROXY = PROXY_LIST[0]
PROXY_HOST = CURRENT_PROXY["host"]
PROXY_PORT = CURRENT_PROXY["port"]
PROXY_USER = CURRENT_PROXY["user"]
PROXY_PASS = CURRENT_PROXY["pass"]
PROXY_URL = get_proxy_url(CURRENT_PROXY)

REQUIRED_CHANNELS = [
    {"username": "TheShadowLogic", "name": "The Shadow Logic", "url": "https://t.me/TheShadowLogic"},
    {"username": "TheEarnEdge", "name": "The Earn Edge", "url": "https://t.me/TheEarnEdge"},
    {"username": "devilagency", "name": "Devil Agency", "url": "https://t.me/devilagency"},
]

db = Database()

class PakistanDatabaseBot:
    def __init__(self):
        self.api_url = "https://pak-data-three.vercel.app/api/lookup"
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def detect_input_type(self, user_input):
        clean_input = re.sub(r'[^0-9]', '', user_input)
        if clean_input.startswith('03') or clean_input.startswith('92'):
            return 'phone'
        elif len(clean_input) == 13:
            return 'cnic'
        else:
            return 'phone'
    
    def convert_number(self, number):
        number = re.sub(r'[^0-9]', '', number)
        if number.startswith('92') and len(number) >= 12:
            number = '0' + number[2:]
        elif number.startswith('0') and len(number) == 11:
            pass
        elif len(number) == 10:
            number = '0' + number
        return number
    
    def format_input(self, user_input):
        input_type = self.detect_input_type(user_input)
        if input_type == 'phone':
            return self.convert_number(user_input), 'phone'
        else:
            clean_cnic = re.sub(r'[^0-9]', '', user_input)
            return clean_cnic, 'cnic'
    
    def api_lookup(self, query):
        """Call the API to lookup data"""
        try:
            response = requests.get(f"{self.api_url}?query={query}", timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API returned status {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"API error: {e}")
            return None
    
    def extract_cnic_from_result(self, api_result):
        """Extract CNIC from phone lookup result"""
        try:
            if api_result and 'results' in api_result:
                data = api_result['results']
                if isinstance(data, list) and len(data) > 0:
                    first_record = data[0]
                    if isinstance(first_record, dict):
                        return first_record.get('cnic') or first_record.get('CNIC')
                elif isinstance(data, dict):
                    return data.get('cnic') or data.get('CNIC')
            return None
        except Exception as e:
            logger.error(f"Error extracting CNIC: {e}")
            return None
    
    def search_sync(self, user_input):
        """Search using API - for phone: get CNIC first, then search CNIC"""
        try:
            logger.info(f"Starting search for: {user_input}")
            formatted_input, input_type = self.format_input(user_input)
            
            if input_type == 'phone':
                logger.info(f"Phone search: {formatted_input}")
                phone_result = self.api_lookup(formatted_input)
                
                if not phone_result or 'results' not in phone_result:
                    logger.info("No phone data found")
                    return None, formatted_input, input_type
                
                cnic = self.extract_cnic_from_result(phone_result)
                if not cnic:
                    logger.info("Could not extract CNIC from phone result")
                    return None, formatted_input, input_type
                
                logger.info(f"Found CNIC: {cnic}, now searching CNIC data")
                cnic_result = self.api_lookup(cnic)
                
                if cnic_result and 'results' in cnic_result:
                    result = self.format_api_result(cnic_result)
                    return result, formatted_input, 'cnic'
                else:
                    return None, formatted_input, input_type
            else:
                logger.info(f"CNIC search: {formatted_input}")
                api_result = self.api_lookup(formatted_input)
                
                if api_result and 'results' in api_result:
                    result = self.format_api_result(api_result)
                    return result, formatted_input, input_type
                else:
                    return None, formatted_input, input_type
                    
        except Exception as e:
            logger.error(f"Error during search: {e}")
            formatted_input, input_type = self.format_input(user_input)
            return None, formatted_input, input_type
    
    def format_api_result(self, api_result):
        """Convert API result to the format expected by the bot"""
        try:
            data = api_result.get('results', [])
            if not data:
                return None
            
            if isinstance(data, dict):
                data = [data]
            
            if not isinstance(data, list) or len(data) == 0:
                return None
            
            first_record = data[0]
            if not isinstance(first_record, dict):
                return None
            
            headers = list(first_record.keys())
            rows = []
            for record in data:
                if isinstance(record, dict):
                    row = [str(record.get(h, '')) for h in headers]
                    rows.append(row)
            
            return {"headers": headers, "data": rows} if rows else None
        except Exception as e:
            logger.error(f"Error formatting API result: {e}")
            return None
    
    def search(self, user_input):
        """Wrapper for backward compatibility"""
        return self.search_sync(user_input)
    
    async def search_async(self, user_input):
        """Async search that runs in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.search_sync, user_input)

bot_instance = PakistanDatabaseBot()

async def check_channel_membership(bot, user_id):
    not_joined = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(f"@{channel['username']}", user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(channel)
        except Exception as e:
            logger.warning(f"Channel check failed for {channel['username']}: {e}")
            not_joined.append(channel)
    return not_joined

def get_join_channels_keyboard(not_joined):
    keyboard = []
    for channel in not_joined:
        keyboard.append([InlineKeyboardButton(f"Join {channel['name']}", url=channel['url'])])
    keyboard.append([InlineKeyboardButton("Verify Joined", callback_data="check_joined")])
    return InlineKeyboardMarkup(keyboard)

def get_force_join_message():
    return """▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
     🚫 ACCESS DENIED 🚫
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

⚠️ Bot use karne ke liye pehle
neeche diye gaye channels join karein:

1️⃣ @jndtech1
2️⃣ @Junaidniz
3️⃣ @xHunterXSigma

✅ Join karne ke baad "Verify Joined"
button dabayein

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""

def get_status_display(user_id=None):
    status = db.get_setting('status') or 'free'
    access = db.get_setting('access') or 'live'
    
    if user_id:
        if user_id == OWNER_ID:
            status = 'owner'
        elif db.is_admin(user_id):
            status = 'admin'
        else:
            user = db.get_user(user_id)
            if user and user[7] == 'premium':
                status = 'premium'
    
    status_icons = {
        'free': 'Free',
        'premium': 'Premium', 
        'admin': 'Admin',
        'owner': 'Owner'
    }
    access_icons = {
        'live': 'Live',
        'maintenance': 'Maintenance'
    }
    
    return status_icons.get(status, 'Free'), access_icons.get(access, 'Live')

def format_copyable_result(data_dict, input_type, search_query, user_id=None):
    if not data_dict: return None
    headers = data_dict.get("headers", [])
    data = data_dict.get("data", [])
    
    type_badge = "📞 *PHONE LOOKUP RESULT* 📞" if input_type == 'phone' else "🪪 *CNIC LOOKUP RESULT* 🪪"
    
    result_lines = []
    result_lines.append("▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭")
    result_lines.append(f"  {type_badge}")
    result_lines.append("▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭")
    result_lines.append("")
    result_lines.append(f"📊 *Total Records:* {len(data)}")
    result_lines.append("")
    
    for idx, row in enumerate(data):
        result_lines.append(f"━━━ 📋 *Record #{idx+1}* ━━━")
        result_lines.append("```")
        
        for j, cell in enumerate(row):
            if j < len(headers) and headers[j]:
                header = headers[j].upper()
                if "NAME" in header and "FATHER" not in header:
                    label = "Name"
                elif "FATHER" in header:
                    label = "Father"
                elif "CNIC" in header:
                    label = "CNIC"
                elif any(x in header for x in ["PHONE", "MOBILE", "NUMBER"]):
                    label = "Phone"
                elif "ADDRESS" in header:
                    label = "Address"
                elif "CITY" in header:
                    label = "City"
                else:
                    label = headers[j]
                
                if "NETWORK" not in header:
                    result_lines.append(f"{label}   : {cell}")
        
        result_lines.append("```")
        result_lines.append("")
    
    result_lines.append("▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭")
    result_lines.append("⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀")
    result_lines.append("▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭")
    
    return "\n".join(result_lines)

def format_not_found(input_type, search_query, user_id=None):
    type_badge = "📞 PHONE LOOKUP 📞" if input_type == 'phone' else "🪪 CNIC LOOKUP 🪪"
    
    result = f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
      {type_badge}
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

❌ Status  : NO DATA FOUND
🔍 Query   : {search_query}

⚠️ Note: Some numbers data is
   not available yet.

💡 Tips:
• Double check the number
• Try without dashes
• Verify 11/13 digits

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""
    return result

async def check_joined_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    not_joined = await check_channel_membership(context.bot, user_id)
    
    if not_joined:
        await query.answer("❌ Abhi bhi channels join nahi hue!", show_alert=True)
    else:
        await query.answer("✅ Verified!", show_alert=True)
        await query.edit_message_text("✅ Verified! Ab aap bot use kar sakte hain.\n\n🔍 Search karne ke liye Phone ya CNIC bhejein.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    referred_by = None
    if args and args[0].startswith('SHADOW-'):
        referrer = db.get_user_by_referral_code(args[0])
        if referrer:
            referred_by = referrer[0]

    is_new = db.add_user(user.id, user.username or user.first_name, referred_by)
    
    if is_new and referred_by:
        try:
            referrer_data = db.get_user(referred_by)
            if referrer_data:
                notification_msg = f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   🎉 *REFERRAL SUCCESS* 🎉
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👤 *New User:* {user.first_name}
💰 *Credits Added:* +5

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
🎯 Keep inviting to earn more!
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=notification_msg,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.warning(f"Failed to send referral notification: {e}")
    
    not_joined = await check_channel_membership(context.bot, user.id)
    if not_joined:
        await update.message.reply_text(
            get_force_join_message(),
            reply_markup=get_join_channels_keyboard(not_joined)
        )
        return
    
    user_data = db.get_user(user.id)
    credits = user_data[2]
    status_display, access_display = get_status_display(user.id)

    welcome_msg = f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
    📱 *PAK SIM DATABASE* 📱
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

⚡ *Status*  : {status_display}
🌐 *Access*  : {access_display}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👤 *User*    : {user.first_name}
💰 *Credits* : {credits}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
       📖 *HOW TO USE* 📖
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

📞 *PHONE SEARCH* (2 Credits)
➤ Send: 03001234567

🪪 *CNIC SEARCH* (5 Credits)
➤ Send: 3520112345678

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
     🎁 *FREE CREDITS* 🎁
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

🎯 /bonus    - Daily 5 Credits
👥 /referral - Invite & Earn 5
🎟️ /redeem   - Use Coupons

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    not_joined = await check_channel_membership(context.bot, update.effective_user.id)
    if not_joined:
        await update.message.reply_text(get_force_join_message(), reply_markup=get_join_channels_keyboard(not_joined))
        return
    
    success, msg = db.check_daily_bonus(update.effective_user.id)
    status = "✅ SUCCESS" if success else "⏳ WAIT"
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
       🎁 *DAILY BONUS* 🎁
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

📊 *Status:* {status}
💬 *Info*  : {msg}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    not_joined = await check_channel_membership(context.bot, update.effective_user.id)
    if not_joined:
        await update.message.reply_text(get_force_join_message(), reply_markup=get_join_channels_keyboard(not_joined))
        return
    
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    referral_code = user_data[5] if user_data else "N/A"
    ref_link = f"https://t.me/{(await context.bot.get_me()).username}?start={referral_code}"
    total_referrals = db.get_referral_count(user_id)
    
    msg = f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
  👥 *REFERRAL PROGRAM* 👥
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

🎁 *Reward:* 5 Credits
💫 Both you and friend get 5!

👥 *Total Referrals:* {total_referrals}

🔑 *Your Code:*
`{referral_code}`

🔗 *Your Link:*
`{ref_link}`

📤 Share to earn credits!

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""
    await update.message.reply_text(msg, parse_mode='Markdown')

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    not_joined = await check_channel_membership(context.bot, update.effective_user.id)
    if not_joined:
        await update.message.reply_text(get_force_join_message(), reply_markup=get_join_channels_keyboard(not_joined))
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /redeem CODE")
        return
    code = context.args[0].upper()
    success, msg = db.redeem_coupon(update.effective_user.id, code)
    status = "✅ SUCCESS" if success else "❌ FAILED"
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
    🎟️ *REDEEM COUPON* 🎟️
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

📊 *Status:* {status}
💬 *Info*  : {msg}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    not_joined = await check_channel_membership(context.bot, update.effective_user.id)
    if not_joined:
        await update.message.reply_text(get_force_join_message(), reply_markup=get_join_channels_keyboard(not_joined))
        return
    
    history = db.get_history(update.effective_user.id)
    if not history:
        await update.message.reply_text("""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   📜 *SEARCH HISTORY* 📜
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

❌ No search history found!

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
        return
    
    lines = ["▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭", "   📜 *SEARCH HISTORY* 📜", "▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭", ""]
    for query, ts, results in history:
        lines.append(f"🔍 *Query:* `{query}`")
        lines.append(f"🕐 *Time* : {ts}")
        lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭")
    lines.append("⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀")
    lines.append("▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭")
    
    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != OWNER_ID and not db.is_admin(user_id):
        return
    
    msg = r"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
      🔐 *ADMIN PANEL* 🔐
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

📊 /stats - Bot Statistics
📢 /broadcast <msg> - Send to all
💰 /addcredits <id> <amt>
💸 /deductcredits <id> <amt>
🎟️ /gen\_coupon <amt> <limit>
👑 /setadmin <id>
🌐 /setaccess <live/maintenance>
⭐ /setstatus <id> <free/premium>
📥 /exportusers - Download XLSX

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""
    await update.message.reply_text(msg, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    users = db.get_all_users()
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
    📊 *BOT STATISTICS* 📊
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👥 *Total Users:* {len(users)}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    if not context.args: return
    msg = " ".join(context.args)
    users = db.get_all_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
       📢 *BROADCAST* 📢
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

{msg}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
            count += 1
        except: pass
    await update.message.reply_text(f"✅ Broadcast sent to {count} users.")

async def add_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    if len(context.args) < 2: 
        await update.message.reply_text("Usage: /addcredits <user_id> <amount>")
        return
    
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount")
        return
    
    # Get old balance
    old_credits = db.get_credits(uid)
    
    # Add new credits (database already does credits + amount)
    db.update_credits(uid, amt)
    
    # Get new balance
    new_credits = db.get_credits(uid)
    
    # Notify admin
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   💰 *CREDITS ADDED* 💰
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👤 *User ID:* `{uid}`
💵 *Added:* +{amt}
📊 *Old Balance:* {old_credits}
✅ *New Balance:* {new_credits}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    
    # Send notification to user
    try:
        await context.bot.send_message(uid, f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   🎉 *CREDITS RECEIVED* 🎉
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

💰 *You received:* +{amt} Credits!
📊 *Old Balance:* {old_credits}
✅ *New Balance:* {new_credits}

🙏 Thank you for using our bot!

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    except Exception as e:
        logger.warning(f"Could not notify user {uid}: {e}")

async def deduct_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    if len(context.args) < 2: 
        await update.message.reply_text("Usage: /deductcredits <user_id> <amount>")
        return
    
    try:
        uid, amt = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount")
        return
    
    old_credits = db.get_credits(uid)
    if old_credits < amt:
        await update.message.reply_text(f"❌ User only has {old_credits} credits")
        return
    
    db.deduct_credits(uid, amt)
    new_credits = db.get_credits(uid)
    
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   💸 *CREDITS DEDUCTED* 💸
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👤 *User ID:* `{uid}`
💵 *Deducted:* -{amt}
📊 *Old Balance:* {old_credits}
✅ *New Balance:* {new_credits}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    
    try:
        await context.bot.send_message(uid, f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   ⚠️ *CREDITS DEDUCTED* ⚠️
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

💸 *Deducted:* -{amt} Credits
📊 *Old Balance:* {old_credits}
✅ *New Balance:* {new_credits}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗦𝗵𝗮𝗱𝗼𝘄 𝗟𝗼𝗴𝗶𝗰 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    except Exception as e:
        logger.warning(f"Could not notify user {uid}: {e}")

async def gen_coupon_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    if len(context.args) < 2: return
    amt, limit = int(context.args[0]), int(context.args[1])
    code = f"SHADOW-{random.randint(1000, 9999)}"
    db.create_coupon(code, amt, limit)
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   🎟️ *COUPON CREATED* 🎟️
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

🔑 *Code*   : `{code}`
💰 *Credits:* {amt}
👥 *Limit*  : {limit}
📊 *Claimed:* 0/{limit}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')

async def set_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: /setaccess live or /setaccess maintenance")
        return
    access = context.args[0].lower()
    if access not in ['live', 'maintenance']:
        await update.message.reply_text("❌ Invalid. Use live or maintenance")
        return
    db.set_setting('access', access)
    
    access_icon = "🟢" if access == 'live' else "🔴"
    
    # Notify admin
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   🌐 *ACCESS UPDATED* 🌐
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

{access_icon} *Status:* {access.title()}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    
    # Broadcast to all users
    users = db.get_all_users()
    count = 0
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   📢 *BOT STATUS UPDATE* 📢
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

{access_icon} *Bot is now:* {access.title()}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
            count += 1
        except:
            pass

async def set_user_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setstatus <user_id> <free/premium/admin>")
        return
    uid = int(context.args[0])
    status = context.args[1].lower()
    if status not in ['free', 'premium', 'admin', 'user']:
        await update.message.reply_text("❌ Invalid. Use free, premium, or admin")
        return
    role = 'user' if status == 'free' else status
    db.set_role(uid, role)
    
    # Notify admin
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   ⭐ *STATUS UPDATED* ⭐
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👤 *User ID:* `{uid}`
📊 *New Status:* {status.title()}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    
    # Broadcast to all users
    users = db.get_all_users()
    count = 0
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   📢 *STATUS UPDATE* 📢
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👤 *User ID:* `{uid}`
📊 *New Status:* {status.title()}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
            count += 1
        except:
            pass

async def set_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /setadmin <user_id>")
        return
    
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")
        return
    
    db.set_role(uid, 'admin')
    
    # Notify owner
    await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   👑 *ADMIN ASSIGNED* 👑
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👤 *User ID:* `{uid}`
📊 *Role:* Admin

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    
    # Notify the new admin
    try:
        await context.bot.send_message(uid, f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   🎉 *CONGRATULATIONS* 🎉
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👑 *You are now an ADMIN!*

🔐 You have access to:
• /admin - Admin Panel
• /stats - Bot Statistics
• /broadcast - Send to all
• /addcredits - Add credits
• /setstatus - Set user status

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    except Exception as e:
        logger.warning(f"Could not notify new admin {uid}: {e}")

async def export_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID and not db.is_admin(update.effective_user.id): return
    
    try:
        import pandas as pd
        users_data = db.get_users_full_data()
        
        if not users_data:
            await update.message.reply_text("❌ No users found")
            return
        
        df = pd.DataFrame(users_data, columns=['User ID', 'Username', 'Joined Date', 'Credits', 'Points', 'Records', 'Role', 'Referral Code'])
        
        file_path = 'data/users_export.xlsx'
        df.to_excel(file_path, index=False)
        
        with open(file_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename='users_export.xlsx',
            caption=f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   📥 *USERS EXPORTED* 📥
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

👥 *Total Users:* {len(users_data)}

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Export error: {e}")
        await update.message.reply_text(f"❌ Export failed: {str(e)}")

async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_input = update.message.text.strip()
    
    not_joined = await check_channel_membership(context.bot, user_id)
    if not_joined:
        await update.message.reply_text(get_force_join_message(), reply_markup=get_join_channels_keyboard(not_joined))
        return
    
    clean_input = re.sub(r'[^0-9]', '', user_input)
    if len(clean_input) < 10:
        await update.message.reply_text("Invalid Input: Too short.")
        return
    
    input_type = bot_instance.detect_input_type(user_input)
    cost = 2 if input_type == 'phone' else 5
    
    is_admin = user_id == OWNER_ID or db.is_admin(user_id)
    user_credits = db.get_credits(user_id)
    
    if not is_admin and user_credits < cost:
        await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
 💸 *INSUFFICIENT CREDITS* 💸
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

⚠️ *Required:* {cost}
💰 *Balance* : {user_credits}

🎯 Use /bonus or /referral!

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
        return

    type_text = "📞 PHONE" if input_type == 'phone' else "🪪 CNIC"
    searching_msg = await update.message.reply_text(f"""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
       🔍 *SEARCHING...* 🔍
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

📝 *Type:* {type_text}
⏳ Please wait...

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗝𝘂𝗻𝗮𝗶𝗱 𝗡𝗶𝘇 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    
    # Use async search with ThreadPoolExecutor for concurrent multi-user support
    result, formatted_input, detected_type = await bot_instance.search_async(user_input)
    
    try: await searching_msg.delete()
    except: pass
    
    if result == "SERVER_ERROR":
        await update.message.reply_text("""▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
   ⚠️ *SERVER ERROR* ⚠️
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

❌ Website is temporarily down
🔄 Please try again in a few minutes

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗦𝗵𝗮𝗱𝗼𝘄 𝗟𝗼𝗴𝗶𝗰 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭""", parse_mode='Markdown')
    elif result:
        if not is_admin: db.update_credits(user_id, -cost)
        user = update.effective_user
        db.add_history(user_id, formatted_input, detected_type, result, user.username, user.first_name)
        response = format_copyable_result(result, detected_type, formatted_input, user_id)
        await update.message.reply_text(response, parse_mode='Markdown')
    else:
        response = format_not_found(detected_type, formatted_input, user_id)
        await update.message.reply_text(response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    not_joined = await check_channel_membership(context.bot, update.effective_user.id)
    if not_joined:
        await update.message.reply_text(get_force_join_message(), reply_markup=get_join_channels_keyboard(not_joined))
        return
    
    help_msg = """▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
      ❓ *HELP CENTER* ❓
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

📞 *PHONE NUMBER*
➤ Format: 03xxxxxxxxx
➤ Cost  : 2 Credits

🪪 *CNIC NUMBER*
➤ Format: xxxxxxxxxxxxx
➤ Cost  : 5 Credits

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
       ⚙️ *COMMANDS* ⚙️
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

🏠 /start    - Main Menu
🎯 /bonus    - Get Credits
👥 /referral - Invite Link
📜 /history  - Last Searches
🎟️ /redeem   - Use Coupons

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗦𝗵𝗮𝗱𝗼𝘄 𝗟𝗼𝗴𝗶𝗰 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    not_joined = await check_channel_membership(context.bot, update.effective_user.id)
    if not_joined:
        await update.message.reply_text(get_force_join_message(), reply_markup=get_join_channels_keyboard(not_joined))
        return
    
    about_msg = """▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
     ℹ️ *ABOUT SYSTEM* ℹ️
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

🔹 *Name*   : Shadow Logic
🔹 *Version:* 5.0 Elite
🔹 *Status* : Operational
🔹 *DB*     : Real-time Sync

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
         ⭐ *WHY US?* ⭐
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭

⚡ Fast Search Results
💾 Excel Auto-Backup
🎁 Referral Rewards
📋 One-Click Copy

▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭
⚡️ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗯𝘆 𝗦𝗵𝗮𝗱𝗼𝘄 𝗟𝗼𝗴𝗶𝗰 🚀
▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭▭"""
    await update.message.reply_text(about_msg, parse_mode='Markdown')

async def set_commands(application: Application):
    user_commands = [
        BotCommand("start", "Main Menu"),
        BotCommand("bonus", "Daily Free Credits"),
        BotCommand("referral", "Invite & Earn"),
        BotCommand("history", "Search History"),
        BotCommand("redeem", "Redeem Coupon"),
        BotCommand("about", "System Info"),
        BotCommand("help", "Help Center"),
    ]
    
    admin_commands = [
        BotCommand("start", "Main Menu"),
        BotCommand("bonus", "Daily Free Credits"),
        BotCommand("referral", "Invite & Earn"),
        BotCommand("history", "Search History"),
        BotCommand("redeem", "Redeem Coupon"),
        BotCommand("about", "System Info"),
        BotCommand("help", "Help Center"),
        BotCommand("admin", "Admin Panel"),
        BotCommand("stats", "Bot Statistics"),
        BotCommand("broadcast", "Send Broadcast"),
        BotCommand("addcredits", "Add Credits"),
        BotCommand("deductcredits", "Deduct Credits"),
        BotCommand("exportusers", "Export Users XLSX"),
        BotCommand("gen_coupon", "Generate Coupon"),
        BotCommand("setaccess", "Set User Access"),
        BotCommand("setstatus", "Set User Status"),
        BotCommand("setadmin", "Assign Admin"),
    ]
    
    from telegram import BotCommandScopeChat, BotCommandScopeDefault
    
    await application.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    
    await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=OWNER_ID))
    
    admins = db.get_all_admins()
    for admin_id in admins:
        try:
            await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except:
            pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, (TimedOut, NetworkError)):
        logger.warning(f"Network error (will retry): {context.error}")
        return
    logger.error(f"Exception: {context.error}")

def main():
    # Create HTTP request with proxy for Telegram API
    request = HTTPXRequest(
        connect_timeout=30.0, 
        read_timeout=30.0, 
        write_timeout=30.0,
        proxy=PROXY_URL
    )
    app = Application.builder().token(BOT_TOKEN).request(request).post_init(set_commands).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("bonus", bonus_command))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("addcredits", add_credits_command))
    app.add_handler(CommandHandler("deductcredits", deduct_credits_command))
    app.add_handler(CommandHandler("exportusers", export_users_command))
    app.add_handler(CommandHandler("gen_coupon", gen_coupon_command))
    app.add_handler(CommandHandler("setaccess", set_access_command))
    app.add_handler(CommandHandler("setstatus", set_user_status_command))
    app.add_handler(CommandHandler("setadmin", set_admin_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_handler(CallbackQueryHandler(check_joined_callback, pattern="check_joined"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))
    
    app.add_error_handler(error_handler)
    
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

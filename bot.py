import os
import re
import math
import time
import json
import asyncio
import yt_dlp
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import UserNotParticipant, ChatAdminRequired

# ═══════════════════════════════════════════
# CONFIGURATION - Environment Variables
# ═══════════════════════════════════════════
# ═══════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════
API_ID = 39860476  # 👈 Apna API_ID dalo (my.telegram.org se)
API_HASH = "65aac2c7469b04ce852850a1fca587d4"  # 👈 Apna API_HASH dalo
BOT_TOKEN = "8286746393:AAG7ZKzqb4oPlkKtqJzXJKx1uSIM85YLzIU"  # 👈 @BotFather se token dalo

# 👑 ADMIN IDS
ADMINS = [8058863815]  # 👈 Apna Telegram ID dalo

# 📢 FORCE SUBSCRIBE
FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", "0"))
FORCE_SUB_USERNAME = os.environ.get("FORCE_SUB_USERNAME", "")

# 💰 SETTINGS
FREE_DAILY_LIMIT = int(os.environ.get("FREE_DAILY_LIMIT", "5"))

PREMIUM_PRICES = {
    "weekly": {"price": 49, "days": 7},
    "monthly": {"price": 149, "days": 30},
    "yearly": {"price": 999, "days": 365},
    "lifetime": {"price": 1999, "days": 36500},
}

# 📁 PATHS
DOWNLOAD_DIR = "downloads"
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# Create directories
for dir_path in [DOWNLOAD_DIR, DATA_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# ═══════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════

def load_json(file_path, default={}):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def get_user(user_id):
    users = load_json(USERS_FILE, {})
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            "joined": datetime.now().isoformat(),
            "downloads_today": 0,
            "total_downloads": 0,
            "last_download_date": "",
            "is_premium": False,
            "premium_expiry": "",
            "name": ""
        }
        save_json(USERS_FILE, users)
    return users[user_id]

def update_user(user_id, data):
    users = load_json(USERS_FILE, {})
    user_id = str(user_id)
    if user_id in users:
        users[user_id].update(data)
    else:
        users[user_id] = data
    save_json(USERS_FILE, users)

def add_premium(user_id, plan):
    users = load_json(USERS_FILE, {})
    user_id = str(user_id)
    
    if user_id not in users:
        get_user(user_id)
        users = load_json(USERS_FILE, {})
    
    days = PREMIUM_PRICES[plan]["days"]
    expiry = datetime.now() + timedelta(days=days)
    
    users[user_id]["is_premium"] = True
    users[user_id]["premium_expiry"] = expiry.isoformat()
    save_json(USERS_FILE, users)

def is_premium(user_id):
    user = get_user(user_id)
    if not user["is_premium"]:
        return False
    
    if user["premium_expiry"]:
        expiry = datetime.fromisoformat(user["premium_expiry"])
        if datetime.now() > expiry:
            update_user(user_id, {"is_premium": False, "premium_expiry": ""})
            return False
    return True

def check_daily_limit(user_id):
    user = get_user(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user["last_download_date"] != today:
        update_user(user_id, {"downloads_today": 0, "last_download_date": today})
        user["downloads_today"] = 0
    
    if is_premium(user_id):
        return True, -1
    
    remaining = FREE_DAILY_LIMIT - user["downloads_today"]
    return remaining > 0, remaining

def increment_download(user_id):
    user = get_user(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    update_user(user_id, {
        "downloads_today": user["downloads_today"] + 1,
        "total_downloads": user["total_downloads"] + 1,
        "last_download_date": today
    })

def get_stats():
    users = load_json(USERS_FILE, {})
    total_users = len(users)
    premium_users = sum(1 for u in users.values() if u.get("is_premium"))
    total_downloads = sum(u.get("total_downloads", 0) for u in users.values())
    
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "free_users": total_users - premium_users,
        "total_downloads": total_downloads
    }

# ═══════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════

MAX_TG_SIZE = 2 * 1024 * 1024 * 1024
user_data = {}

PLATFORMS = {
    'youtube.com': '🔴 YouTube',
    'youtu.be': '🔴 YouTube',
    'instagram.com': '📸 Instagram',
    'facebook.com': '🔵 Facebook',
    'fb.watch': '🔵 Facebook',
    'tiktok.com': '🎵 TikTok',
    'twitter.com': '🐦 Twitter',
    'x.com': '🐦 Twitter',
    'vimeo.com': '🎬 Vimeo',
    'reddit.com': '🟠 Reddit',
    'pinterest.com': '📌 Pinterest',
    'twitch.tv': '💜 Twitch',
    'dailymotion.com': '📺 Dailymotion',
}

# Initialize bot
app = Client(
    "railway_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ═══════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════

def detect_platform(url):
    for domain, name in PLATFORMS.items():
        if domain in url.lower():
            return name
    return '🌐 Website'

def is_valid_url(text):
    return re.match(r'https?://\S+', text, re.IGNORECASE) is not None

def format_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def format_time(seconds):
    if seconds < 0:
        return "∞"
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds//60)}m {int(seconds%60)}s"
    else:
        return f"{int(seconds//3600)}h {int((seconds%3600)//60)}m"

def format_speed(speed):
    if speed < 1024:
        return f"{speed:.0f} B/s"
    elif speed < 1024 * 1024:
        return f"{speed/1024:.1f} KB/s"
    else:
        return f"{speed/(1024*1024):.1f} MB/s"

def is_admin(user_id):
    return user_id in ADMINS

# ═══════════════════════════════════════════
# FORCE SUBSCRIBE
# ═══════════════════════════════════════════

async def check_force_sub(client, user_id):
    if is_admin(user_id) or is_premium(user_id):
        return True
    
    if FORCE_SUB_CHANNEL == 0:
        return True
    
    try:
        await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except:
        return True

def get_force_sub_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 Join Channel", url=f"https://t.me/{FORCE_SUB_USERNAME}")],
        [InlineKeyboardButton("✅ Joined - Check", callback_data="check_sub")]
    ])

# ═══════════════════════════════════════════
# YT-DLP OPTIONS
# ═══════════════════════════════════════════

def get_fast_ydl_opts(filename, format_opt, progress_hook=None, is_audio=False):
    opts = {
        'format': format_opt,
        'outtmpl': f'{filename}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'concurrent_fragment_downloads': 4,
        'buffersize': 1024 * 1024 * 16,
        'http_chunk_size': 10485760,
        'retries': 10,
        'fragment_retries': 10,
        'socket_timeout': 30,
        'extractor_retries': 3,
        
        # ⭐ Format fallback - Important!
        'format_sort': ['res:1080', 'ext:mp4:m4a'],
        'merge_output_format': 'mp4',
    }
    
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]
    
    if is_audio:
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
    
    return opts

# ═══════════════════════════════════════════
# PROGRESS TRACKER
# ═══════════════════════════════════════════

class DownloadProgress:
    def __init__(self, status_msg):
        self.status_msg = status_msg
        self.last_update = 0
        self.start_time = time.time()
    
    def hook(self, d):
        if d['status'] == 'downloading':
            try:
                current_time = time.time()
                if current_time - self.last_update < 3:
                    return
                self.last_update = current_time
                
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed') or 0
                eta = d.get('eta') or 0
                
                if total > 0:
                    percentage = (downloaded / total) * 100
                    filled = int(percentage // 5)
                    bar = "█" * filled + "░" * (20 - filled)
                    
                    text = (
                        f"⚡ <b>Downloading...</b>\n\n"
                        f"<code>[{bar}]</code> {percentage:.1f}%\n\n"
                        f"📊 {format_size(downloaded)} / {format_size(total)}\n"
                        f"🚀 Speed: {format_speed(speed)}\n"
                        f"⏱ ETA: {format_time(eta)}"
                    )
                    
                    asyncio.get_event_loop().create_task(self.safe_edit(text))
            except:
                pass
    
    async def safe_edit(self, text):
        try:
            await self.status_msg.edit_text(text, parse_mode=enums.ParseMode.HTML)
        except:
            pass

async def upload_progress(current, total, message, start_time, action="📤 Uploading"):
    try:
        now = time.time()
        if not hasattr(upload_progress, 'last_update'):
            upload_progress.last_update = 0
        
        if now - upload_progress.last_update < 3:
            return
        upload_progress.last_update = now
        
        elapsed = now - start_time
        percentage = (current / total) * 100
        speed = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0
        
        filled = int(percentage // 5)
        bar = "█" * filled + "░" * (20 - filled)
        
        text = (
            f"{action}\n\n"
            f"<code>[{bar}]</code> {percentage:.1f}%\n\n"
            f"📊 {format_size(current)} / {format_size(total)}\n"
            f"🚀 Speed: {format_speed(speed)}"
        )
        
        await message.edit_text(text, parse_mode=enums.ParseMode.HTML)
    except:
        pass

# ═══════════════════════════════════════════
# BOT COMMANDS
# ═══════════════════════════════════════════

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    get_user(user_id)
    update_user(user_id, {"name": user_name})
    
    if not await check_force_sub(client, user_id):
        await message.reply_text(
            f"👋 <b>Welcome {user_name}!</b>\n\n"
            f"⚠️ Pehle channel join karo:",
            reply_markup=get_force_sub_keyboard(),
            parse_mode=enums.ParseMode.HTML
        )
        return
    
    premium_status = "⭐ Premium" if is_premium(user_id) else "🆓 Free"
    can_download, remaining = check_daily_limit(user_id)
    limit_text = "Unlimited" if remaining == -1 else f"{remaining}/{FREE_DAILY_LIMIT}"
    
    await message.reply_text(
        f"🚀 <b>VIDEO DOWNLOADER BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Welcome <b>{user_name}</b>!\n\n"
        f"📊 Status: {premium_status}\n"
        f"📥 Today's Limit: {limit_text}\n\n"
        f"✅ <b>Supported:</b>\n"
        f"YouTube • Instagram • TikTok\n"
        f"Facebook • Twitter • 1000+ more\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 <b>Bas link bhejo!</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Premium", callback_data="premium_plans"),
             InlineKeyboardButton("📊 Stats", callback_data="my_stats")]
        ]),
        parse_mode=enums.ParseMode.HTML
    )

@app.on_message(filters.command("admin") & filters.user(ADMINS))
async def admin_panel(client, message: Message):
    stats = get_stats()
    
    await message.reply_text(
        f"👑 <b>ADMIN PANEL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total Users: {stats['total_users']}\n"
        f"⭐ Premium: {stats['premium_users']}\n"
        f"📥 Downloads: {stats['total_downloads']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")]
        ]),
        parse_mode=enums.ParseMode.HTML
    )

@app.on_message(filters.command("addpremium") & filters.user(ADMINS))
async def add_premium_cmd(client, message: Message):
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.reply_text("Usage: /addpremium USER_ID PLAN\n\nPlans: weekly, monthly, yearly, lifetime")
            return
        
        user_id = int(args[1])
        plan = args[2].lower()
        
        if plan not in PREMIUM_PRICES:
            await message.reply_text("❌ Invalid plan!")
            return
        
        add_premium(user_id, plan)
        await message.reply_text(f"✅ Premium added!\nUser: {user_id}\nPlan: {plan}")
        
        try:
            await client.send_message(user_id, f"🎉 You are now Premium!\nPlan: {plan.title()}")
        except:
            pass
            
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_cmd(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("❌ Reply to a message!")
        return
    
    users = load_json(USERS_FILE, {})
    sent = 0
    failed = 0
    
    status_msg = await message.reply_text("📢 Broadcasting...")
    
    for user_id in users.keys():
        try:
            await message.reply_to_message.copy(int(user_id))
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)
    
    await status_msg.edit_text(f"📢 Done!\n✅ Sent: {sent}\n❌ Failed: {failed}")

@app.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_cmd(client, message: Message):
    stats = get_stats()
    await message.reply_text(
        f"📊 <b>STATS</b>\n\n"
        f"👥 Users: {stats['total_users']}\n"
        f"⭐ Premium: {stats['premium_users']}\n"
        f"📥 Downloads: {stats['total_downloads']}",
        parse_mode=enums.ParseMode.HTML
    )

# ═══════════════════════════════════════════
# HANDLE LINKS
# ═══════════════════════════════════════════

@app.on_message(filters.text & ~filters.command(["start", "admin", "addpremium", "broadcast", "stats"]))
async def handle_link(client, message: Message):
    url = message.text.strip()
    user_id = message.from_user.id
    
    if not is_valid_url(url):
        return
    
    if not await check_force_sub(client, user_id):
        await message.reply_text(
            "⚠️ Pehle channel join karo!",
            reply_markup=get_force_sub_keyboard(),
            parse_mode=enums.ParseMode.HTML
        )
        return
    
    can_download, remaining = check_daily_limit(user_id)
    if not can_download:
        await message.reply_text(
            "⚠️ <b>Daily limit reached!</b>\n\n⭐ Get Premium for unlimited!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Get Premium", callback_data="premium_plans")]
            ]),
            parse_mode=enums.ParseMode.HTML
        )
        return
    
    platform = detect_platform(url)
    limit_text = "" if is_premium(user_id) else f"\n📊 Remaining: {remaining}/{FREE_DAILY_LIMIT}"
    
    status_msg = await message.reply_text(
        f"🔍 {platform} detected!{limit_text}\n⏳ Downloading...",
        parse_mode=enums.ParseMode.HTML
    )
    
    try:
        # Direct download - no quality selection (simpler & faster)
        filename = os.path.join(DOWNLOAD_DIR, f"{user_id}_{int(time.time())}")
        
        progress = DownloadProgress(status_msg)
        
        ydl_opts = {
            'format': 'bv*+ba/b',  # Best video+audio, fallback to best
            'outtmpl': f'{filename}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'progress_hooks': [progress.hook],
            'concurrent_fragment_downloads': 4,
            'retries': 5,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            title = info.get('title', 'Video')[:50]
        
        # Find downloaded file
        actual_file = f"{filename}.{ext}"
        if not os.path.exists(actual_file):
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(f"{user_id}_"):
                    actual_file = os.path.join(DOWNLOAD_DIR, f)
                    break
        
        if os.path.exists(actual_file):
            increment_download(user_id)
            await send_file(client, user_id, actual_file, title, platform, status_msg)
        else:
            await status_msg.edit_text("❌ Download failed! Try again.")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}")
# ═══════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════

@app.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    message = callback_query.message
    
    await callback_query.answer()
    
    if data == "check_sub":
        if await check_force_sub(client, user_id):
            await message.edit_text("✅ Thanks! Ab link bhejo!", parse_mode=enums.ParseMode.HTML)
        else:
            await message.edit_text("⚠️ Channel join karo!", reply_markup=get_force_sub_keyboard(), parse_mode=enums.ParseMode.HTML)
        return
    
    if data == "premium_plans":
        await message.edit_text(
            f"⭐ <b>PREMIUM PLANS</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Weekly: ₹{PREMIUM_PRICES['weekly']['price']}\n"
            f"💰 Monthly: ₹{PREMIUM_PRICES['monthly']['price']}\n"
            f"💰 Yearly: ₹{PREMIUM_PRICES['yearly']['price']}\n"
            f"💰 Lifetime: ₹{PREMIUM_PRICES['lifetime']['price']}\n\n"
            f"✅ Benefits:\n• Unlimited downloads\n• No ads\n• Fast speed\n\n"
            f"📩 Contact: @YourUsername",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Buy Now", url="https://t.me/YourUsername")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ]),
            parse_mode=enums.ParseMode.HTML
        )
        return
    
    if data == "my_stats":
        user = get_user(user_id)
        premium_text = "⭐ Premium" if is_premium(user_id) else "🆓 Free"
        
        await message.edit_text(
            f"📊 <b>YOUR STATS</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Status: {premium_text}\n"
            f"📥 Today: {user['downloads_today']}\n"
            f"📊 Total: {user['total_downloads']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]),
            parse_mode=enums.ParseMode.HTML
        )
        return
    
    if data == "back_home":
        await start_command(client, message)
        return
    
    if data.startswith("dl_"):
        can_download, remaining = check_daily_limit(user_id)
        if not can_download:
            await message.edit_text("⚠️ Daily limit reached!")
            return
        
        if user_id not in user_data:
            await message.edit_text("⚠️ Session expired! Send link again.")
            return
        
        url = user_data[user_id]['url']
        title = user_data[user_id]['title']
        platform = user_data[user_id]['platform']
        choice = data.replace("dl_", "")
        
        
        await message.edit_text("⚡ <b>Downloading...</b>", parse_mode=enums.ParseMode.HTML)
        
        try:
            filename = os.path.join(DOWNLOAD_DIR, f"{user_id}_{int(time.time())}")
            is_audio = choice == "audio"
            
            if choice == "best":
                format_opt = 'bv*+ba/b'
            elif choice == "audio":
                format_opt = 'ba/b'
            elif choice == "quick":
                format_opt = 'b'
            else:
                height = choice.replace("q_", "")
                format_opt = f'bv*[height<={height}]+ba/b[height<={height}]/b'
            
            progress = DownloadProgress(message)
            ydl_opts = get_fast_ydl_opts(filename, format_opt, progress.hook, is_audio)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                ext = 'mp3' if is_audio else info.get('ext', 'mp4')
            
            actual_file = None
            for e in ['mp4', 'mkv', 'webm', 'mp3', 'm4a', ext]:
                test_file = f"{filename}.{e}"
                if os.path.exists(test_file):
                    actual_file = test_file
                    break
            
            if not actual_file:
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(f"{user_id}_"):
                        actual_file = os.path.join(DOWNLOAD_DIR, f)
                        break
            
            if actual_file and os.path.exists(actual_file):
                increment_download(user_id)
                await send_file(client, user_id, actual_file, title, platform, message, is_audio)
                if user_id in user_data:
                    del user_data[user_id]
            else:
                await message.edit_text("❌ Download failed!")
                
        except Exception as e:
            await message.edit_text(f"❌ Error: {str(e)[:100]}")

async def send_file(client, chat_id, file_path, title, platform, status_msg, is_audio=False):
    if not os.path.exists(file_path):
        await status_msg.edit_text("❌ File not found!")
        return
    
    file_size = os.path.getsize(file_path)
    
    try:
        await status_msg.edit_text(f"📤 <b>Uploading...</b>\n📊 Size: {format_size(file_size)}", parse_mode=enums.ParseMode.HTML)
        
        start_time = time.time()
        
        if is_audio or file_path.endswith(('.mp3', '.m4a')):
            await client.send_audio(
                chat_id=chat_id,
                audio=file_path,
                caption=f"🎵 <b>{title}</b>\n{platform}",
                parse_mode=enums.ParseMode.HTML,
                progress=upload_progress,
                progress_args=(status_msg, start_time, "📤 Uploading")
            )
        else:
            await client.send_video(
                chat_id=chat_id,
                video=file_path,
                caption=f"📹 <b>{title}</b>\n{platform}",
                parse_mode=enums.ParseMode.HTML,
                supports_streaming=True,
                progress=upload_progress,
                progress_args=(status_msg, start_time, "📤 Uploading")
            )
        
        os.remove(file_path)
        
        elapsed = time.time() - start_time
        await status_msg.edit_text(
            f"✅ <b>Done!</b> 🎉\n📹 {title}\n📊 {format_size(file_size)} • {format_time(elapsed)}",
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}")
        if os.path.exists(file_path):
            os.remove(file_path)

# ═══════════════════════════════════════════
# CLEANUP TASK
# ═══════════════════════════════════════════

async def cleanup_downloads():
    """Delete old files every hour"""
    while True:
        try:
            current_time = time.time()
            for filename in os.listdir(DOWNLOAD_DIR):
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                if os.path.isfile(filepath):
                    if current_time - os.path.getmtime(filepath) > 3600:
                        os.remove(filepath)
        except:
            pass
        await asyncio.sleep(3600)

# ═══════════════════════════════════════════
# RUN BOT
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚂 RAILWAY VIDEO DOWNLOADER BOT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ Starting...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    app.run()
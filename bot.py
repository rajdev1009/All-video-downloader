import os
import asyncio
import logging
import subprocess
import json
import time
from threading import Thread

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from flask import Flask

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
API_ID   = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  FLASK HEALTH-CHECK
# ─────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot is running perfectly!", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ─────────────────────────────────────────
#  PYROGRAM CLIENT
# ─────────────────────────────────────────
app = Client("video_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data: dict = {}

# ─────────────────────────────────────────
#  2026 BYPASS HEADERS & SETTINGS
# ─────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
COOKIES_FILE = "cookies.txt" # Ensure this file is in your repo if links fail

def get_yt_dlp_base_cmd(url: str):
    """Returns the base command with all bypass flags for 2026."""
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--user-agent", USER_AGENT,
        "--no-check-certificate",
        "--geo-bypass",
        "--add-header", "Accept-Language:en-US,en;q=0.9",
        "--referer", "https://www.google.com/"
    ]
    # Agar cookies.txt maujood hai toh use use karein
    if os.path.exists(COOKIES_FILE):
        cmd.extend(["--cookies", COOKIES_FILE])
    return cmd

def get_formats(url: str) -> list[dict]:
    cmd = get_yt_dlp_base_cmd(url) + ["--dump-json", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"yt-dlp error: {result.stderr}")
            return []
        
        info = json.loads(result.stdout)
        formats = info.get("formats", [])

        seen_heights = set()
        quality_list = []
        for f in reversed(formats):
            height = f.get("height")
            ext    = f.get("ext", "mp4")
            fmt_id = f.get("format_id")
            if height and height not in seen_heights and height <= 1080:
                seen_heights.add(height)
                quality_list.append({
                    "format_id": fmt_id,
                    "height": height,
                    "ext": ext,
                    "label": f"{height}p  ({ext})"
                })
        return quality_list[:6]
    except Exception as e:
        logger.error(f"get_formats exception: {e}")
        return []

# ─────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text(
        "👋 **AstraToonix Video Downloader (2026 Edition)**\n\n"
        "Send me any link from YouTube, Insta, or FB.\n"
        "I will fetch HD qualities for you! ✅"
    )

@app.on_message(filters.text & filters.private)
async def handle_link(client: Client, message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return

    status_msg = await message.reply_text("🔍 Analyzing link (Bypassing security)...")
    
    # Run in executor to avoid blocking
    formats = await asyncio.get_event_loop().run_in_executor(None, get_formats, url)

    if not formats:
        await status_msg.edit_text(
            "❌ **Could not fetch formats.**\n\n"
            "Possible reasons:\n"
            "1. YouTube/Insta blocked the server IP.\n"
            "2. Link is private or age-restricted.\n"
            "3. `cookies.txt` is missing or expired."
        )
        return

    user_id = message.from_user.id
    user_data[user_id] = {"url": url, "formats": formats}

    buttons = []
    for idx, fmt in enumerate(formats):
        buttons.append([InlineKeyboardButton(f"📥 {fmt['label']}", callback_data=f"dl|{user_id}|{idx}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel")])

    await status_msg.edit_text(
        "✅ Link detected! Choose quality:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^dl\|"))
async def download_cb(client: Client, cb: CallbackQuery):
    _, uid_str, idx_str = cb.data.split("|")
    user_id, idx = int(uid_str), int(idx_str)

    if user_id not in user_data:
        await cb.answer("Expired. Send link again.", show_alert=True)
        return

    url = user_data[user_id]["url"]
    fmt = user_data[user_id]["formats"][idx]

    await cb.answer("Download started...")
    status_msg = await cb.message.edit_text(f"⬇️ Downloading `{fmt['label']}`...")

    output_path = os.path.join(DOWNLOAD_DIR, f"{user_id}_{int(time.time())}.mp4")
    
    cmd = get_yt_dlp_base_cmd(url) + [
        "-f", f"{fmt['format_id']}+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]

    try:
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.wait()

        if not os.path.exists(output_path):
            await status_msg.edit_text("❌ Download failed at server level.")
            return

        await status_msg.edit_text("📤 Uploading to Telegram...")
        await client.send_video(
            chat_id=cb.message.chat.id,
            video=output_path,
            caption=f"✅ Quality: {fmt['label']}\n🚀 Powered by AstraToonix",
            supports_streaming=True
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)
        user_data.pop(user_id, None)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    app.run()

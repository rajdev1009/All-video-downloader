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
#  CONFIGURATION  –  Set via Environment Variables on Render
# ─────────────────────────────────────────
API_ID   = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  FLASK HEALTH-CHECK SERVER  (keeps Render alive)
# ─────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot is running!", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ─────────────────────────────────────────
#  PYROGRAM BOT CLIENT
# ─────────────────────────────────────────
app = Client("video_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory store: { user_id: { "url": ..., "formats": [...] } }
user_data: dict = {}

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
SUPPORTED_DOMAINS = ("youtube.com", "youtu.be", "instagram.com", "facebook.com", "fb.watch")

def is_supported(url: str) -> bool:
    return any(d in url for d in SUPPORTED_DOMAINS)

def detect_platform(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "🎬 YouTube"
    if "instagram.com" in url:
        return "📸 Instagram"
    if "facebook.com" in url or "fb.watch" in url:
        return "📘 Facebook"
    return "🌐 Unknown"

def get_formats(url: str) -> list[dict]:
    """Return list of available video formats via yt-dlp JSON."""
    cmd = ["yt-dlp", "--dump-json", "--no-playlist", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return []
        info = json.loads(result.stdout)
        formats = info.get("formats", [])

        # Keep only video+audio combined OR video-only formats with a height
        seen_heights = set()
        quality_list = []
        for f in reversed(formats):          # best quality first
            height = f.get("height")
            ext    = f.get("ext", "mp4")
            fmt_id = f.get("format_id")
            if height and height not in seen_heights:
                seen_heights.add(height)
                quality_list.append({
                    "format_id": fmt_id,
                    "height": height,
                    "ext": ext,
                    "label": f"{height}p  ({ext})"
                })
        # Limit to 5 options
        return quality_list[:5]
    except Exception as e:
        logger.error(f"get_formats error: {e}")
        return []

def build_quality_buttons(user_id: int, formats: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for idx, fmt in enumerate(formats):
        buttons.append([
            InlineKeyboardButton(
                text=f"📥 {fmt['label']}",
                callback_data=f"dl|{user_id}|{idx}"
            )
        ])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel|{user_id}")])
    return InlineKeyboardMarkup(buttons)

async def progress_hook(current: int, total: int, message: Message, start_time: float):
    """Edit message with upload progress."""
    if total == 0:
        return
    pct   = current * 100 // total
    done  = pct // 5          # each block = 5 %
    bar   = "█" * done + "░" * (20 - done)
    speed = current / (time.time() - start_time + 0.001)
    speed_kb = speed / 1024
    try:
        await message.edit_text(
            f"📤 **Uploading…**\n`[{bar}]` **{pct}%**\n"
            f"Speed: `{speed_kb:.1f} KB/s`"
        )
    except Exception:
        pass   # ignore flood-wait etc.

# ─────────────────────────────────────────
#  BOT HANDLERS
# ─────────────────────────────────────────
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text(
        "👋 **Welcome to Video Downloader Bot!**\n\n"
        "🔗 Just send me a link from:\n"
        "  • 🎬 YouTube\n"
        "  • 📸 Instagram Reels\n"
        "  • 📘 Facebook\n\n"
        "I'll show you quality options and download it for you! ✅"
    )

@app.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        "📖 **How to use:**\n"
        "1. Send any YouTube / Instagram / Facebook link\n"
        "2. Choose your preferred quality\n"
        "3. Wait for the download & upload\n\n"
        "⚠️ Large files (>2 GB) may fail due to Telegram limits."
    )

@app.on_message(filters.text & filters.private)
async def handle_link(client: Client, message: Message):
    url = message.text.strip()
    if not is_supported(url):
        await message.reply_text(
            "❌ **Unsupported link!**\n"
            "Please send a YouTube, Instagram, or Facebook URL."
        )
        return

    platform = detect_platform(url)
    status_msg = await message.reply_text(f"🔍 Fetching formats for {platform}…")

    formats = await asyncio.get_event_loop().run_in_executor(None, get_formats, url)

    if not formats:
        await status_msg.edit_text(
            "⚠️ Could not fetch formats.\n"
            "The link may be private, age-restricted, or unsupported."
        )
        return

    user_id = message.from_user.id
    user_data[user_id] = {"url": url, "formats": formats}

    await status_msg.edit_text(
        f"✅ **{platform}** link detected!\n"
        f"Choose your preferred quality 👇",
        reply_markup=build_quality_buttons(user_id, formats)
    )

@app.on_callback_query(filters.regex(r"^cancel\|"))
async def cancel_cb(client: Client, cb: CallbackQuery):
    uid = int(cb.data.split("|")[1])
    user_data.pop(uid, None)
    await cb.message.edit_text("🚫 Download cancelled.")

@app.on_callback_query(filters.regex(r"^dl\|"))
async def download_cb(client: Client, cb: CallbackQuery):
    _, uid_str, idx_str = cb.data.split("|")
    user_id = int(uid_str)
    idx     = int(idx_str)

    if user_id not in user_data:
        await cb.answer("Session expired. Send the link again.", show_alert=True)
        return

    url     = user_data[user_id]["url"]
    formats = user_data[user_id]["formats"]
    fmt     = formats[idx]

    await cb.answer()
    status_msg = await cb.message.edit_text(
        f"⬇️ **Downloading** `{fmt['label']}`…\n`[░░░░░░░░░░░░░░░░░░░░]` 0%"
    )

    output_template = os.path.join(DOWNLOAD_DIR, f"{user_id}_%(title).60s.%(ext)s")

    # 2026 Updated yt-dlp command for HD & Security bypass
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[height<=1080]+bestaudio/best",  # Strict 1080p for Telegram 2GB limit
        "--merge-output-format", "mp4",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "--referer", "https://www.youtube.com/",
        "--no-check-certificate",
        "--geo-bypass",
        "--sleep-interval", "3",  # Rate-limit se bachne ke liye
        "--newline",
        "-o", output_template,
        url
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        last_edit = 0
        downloaded_file = None

        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="ignore").strip()

            # Parse yt-dlp progress lines
            if "[download]" in line and "%" in line:
                try:
                    pct_str = line.split("%")[0].split()[-1]
                    pct     = float(pct_str)
                    done    = int(pct / 5)
                    bar     = "█" * done + "░" * (20 - done)
                    now     = time.time()
                    if now - last_edit > 2:          # throttle edits
                        await status_msg.edit_text(
                            f"⬇️ **Downloading** `{fmt['label']}`…\n"
                            f"`[{bar}]` **{pct:.1f}%**"
                        )
                        last_edit = now
                except Exception:
                    pass

            # Capture the final filename
            if "[Merger]" in line or "Destination:" in line or "[download] Destination:" in line:
                parts = line.split("Destination:")
                if len(parts) > 1:
                    downloaded_file = parts[1].strip()

        await proc.wait()

        # If we didn't capture via Merger line, glob for the file
        if not downloaded_file:
            import glob
            files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{user_id}_*.mp4"))
            if files:
                downloaded_file = max(files, key=os.path.getctime)

        if not downloaded_file or not os.path.exists(downloaded_file):
            await status_msg.edit_text("❌ Download failed. The file was not created.")
            return

        file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
        if file_size_mb > 2000:
            await status_msg.edit_text(
                f"❌ File too large ({file_size_mb:.1f} MB).\n"
                "Telegram bots can only upload files up to 2 GB."
            )
            os.remove(downloaded_file)
            return

        await status_msg.edit_text("📤 **Uploading to Telegram…**\n`[░░░░░░░░░░░░░░░░░░░░]` 0%")
        start_time = time.time()

        await client.send_video(
            chat_id=cb.message.chat.id,
            video=downloaded_file,
            caption=f"✅ Downloaded in **{fmt['label']}**\n🤖 @YourBotUsername",
            supports_streaming=True,
            progress=progress_hook,
            progress_args=(status_msg, start_time),
        )

        await status_msg.edit_text("✅ **Done!** Video sent successfully.")

    except Exception as e:
        logger.error(f"Download/upload error: {e}")
        await status_msg.edit_text(f"❌ Error: `{e}`")
    finally:
        # Cleanup — delete file from server
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            logger.info(f"Cleaned up: {downloaded_file}")
        user_data.pop(user_id, None)

# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
if __name__ == "__main__":
    # Start Flask in background thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask health-check server started.")

    # Start Pyrogram bot
    logger.info("Starting Telegram bot…")
    app.run()

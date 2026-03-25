# 🎬 Telegram Video Downloader Bot — Setup Guide

## 📁 Files
| File | Purpose |
|------|---------|
| `bot.py` | Main bot code |
| `requirements.txt` | Python dependencies |
| `render.yaml` | Render.com deployment config |

---

## 🔑 Step 1 — Get Credentials

### Telegram API Credentials
1. Go to https://my.telegram.org
2. Log in → "API Development Tools"
3. Create a new app → copy **API_ID** and **API_HASH**

### Bot Token
1. Open Telegram → search `@BotFather`
2. Send `/newbot` → follow steps
3. Copy the **BOT_TOKEN**

---

## 🖥️ Step 2 — Run Locally (Test First)

```bash
# 1. Clone / place all files in a folder
# 2. Install dependencies
pip install -r requirements.txt

# 3. Install ffmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg
# macOS:
brew install ffmpeg

# 4. Set environment variables
export API_ID=12345678
export API_HASH=your_api_hash_here
export BOT_TOKEN=your_bot_token_here

# 5. Run
python bot.py
```

---

## ☁️ Step 3 — Deploy on Render.com (FREE)

1. Push all 3 files to a **GitHub repo**
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Set **Build Command**:
   ```
   pip install -r requirements.txt && apt-get install -y ffmpeg
   ```
5. Set **Start Command**:
   ```
   python bot.py
   ```
6. Add **Environment Variables** in Render dashboard:
   - `API_ID` = your api id
   - `API_HASH` = your api hash
   - `BOT_TOKEN` = your bot token
7. Click **Deploy** ✅

### Keep Bot Alive (Prevent Sleep)
- Use https://uptimerobot.com (free)
- Add HTTP monitor pointing to your Render URL (e.g. `https://your-bot.onrender.com`)
- Set check interval: **5 minutes**

---

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Usage instructions |
| Send any link | Auto-detects & shows quality buttons |

---

## ✨ Features

- ✅ YouTube, Instagram Reels, Facebook support
- ✅ Inline quality buttons (360p / 720p / 1080p etc.)
- ✅ HD download with FFmpeg audio+video merge
- ✅ Real-time progress bar (download + upload)
- ✅ Auto file cleanup after upload
- ✅ Flask health-check for Render.com

---

## ⚠️ Important Notes

- Telegram bot file size limit = **2 GB**
- Instagram private posts **cannot** be downloaded
- YouTube age-restricted videos may fail
- Replace `@YourBotUsername` in `bot.py` with your actual bot username

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `ffmpeg not found` | Install ffmpeg & update path in cmd |
| `Session expired` | Send the link again |
| Download fails | Video may be private/geo-restricted |
| Bot sleeps on Render | Set up UptimeRobot monitor |

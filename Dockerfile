# Python 3.10+ standsrd image (March 2026 updated)
FROM python:3.10-slim

# System updates aur FFmpeg 8+ install karne ke liye
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Working directory set karein
WORKDIR /app

# Requirements ko copy karke install karein
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Baaki saari files (bot.py, cookies.txt etc.) copy karein
COPY . .

# Flask port ko expose karein (Koyeb/Render ke liye)
EXPOSE 8080

# Bot ko chalane ka command
CMD ["python", "bot.py"]

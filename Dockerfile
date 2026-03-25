# Python ka official image use karein
FROM python:3.10-slim

# System updates aur FFmpeg install karein
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Working directory set karein
WORKDIR /app

# Requirements copy aur install karein
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baaki saara code copy karein
COPY . .

# Flask port ko expose karein
EXPOSE 8080

# Bot ko start karne ka command
CMD ["python", "bot.py"]

# ---------------------------------------------------------------------
# 🐍 Base image
# ---------------------------------------------------------------------
FROM python:3.11-slim

# ---------------------------------------------------------------------
# 🎧 Install system dependencies (FFmpeg for audio)
# ---------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------
# 📁 Set working directory inside container
# ---------------------------------------------------------------------
WORKDIR /app

# ---------------------------------------------------------------------
# 📦 Copy requirements and install Python dependencies
# ---------------------------------------------------------------------
COPY requirements.txt .

# 🧹 Force cache busting so Render rebuilds dependencies fresh
ARG CACHEBUST=1

# 🧩 Force pip upgrade and reinstall all deps (important for websockets>=12)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------
# 📂 Copy the rest of your application files
# ---------------------------------------------------------------------
COPY . .

# ---------------------------------------------------------------------
# 🔥 Expose port (Render automatically maps $PORT)
# ---------------------------------------------------------------------
EXPOSE 10000

# ---------------------------------------------------------------------
# 🚀 Run your Flask realtime app
# ---------------------------------------------------------------------
CMD ["python", "realtime_agent.py"]
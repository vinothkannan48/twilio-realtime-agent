# ---------------------------------------------------------------------
# 🐍 Base image
# ---------------------------------------------------------------------
FROM python:3.11-slim

# ---------------------------------------------------------------------
# 🎧 Install system dependencies
# ---------------------------------------------------------------------
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------
# 📁 Working directory
# ---------------------------------------------------------------------
WORKDIR /app

# ---------------------------------------------------------------------
# 📦 Copy and install dependencies (force rebuild)
# ---------------------------------------------------------------------
COPY requirements.txt .

# Disable Docker layer caching completely
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --force-reinstall websockets==15.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------
# 📂 Copy application files
# ---------------------------------------------------------------------
COPY . .

EXPOSE 10000
CMD ["python", "realtime_agent.py"]
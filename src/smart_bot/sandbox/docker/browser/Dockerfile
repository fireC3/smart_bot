FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    xvfb xauth \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libdrm2 \
    libxcb1 libxkbcommon0 libxcomposite1 libxrandr2 libxdamage1 \
    libxfixes3 libcups2 libdbus-1-3 libpango-1.0-0 libcairo2 libasound2 \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 playwright 浏览器
RUN playwright install chromium

COPY . .

CMD xvfb-run --auto-servernum uvicorn main:app --host 0.0.0.0 --port 8000
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_PATH=/usr/bin/chromium \
    CHROME_HEADLESS=false \
    DATA_DIR=/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium xvfb ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot_crawler.py .

RUN useradd --create-home --uid 10001 bot \
    && mkdir -p /data \
    && chown -R bot:bot /app /data

USER bot
VOLUME ["/data"]
CMD ["xvfb-run", "-a", "python", "bot_crawler.py"]
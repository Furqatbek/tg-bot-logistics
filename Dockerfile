# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/data/bot.db

WORKDIR /app

# Dependencies first so code edits don't invalidate the install layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# SQLite lives on a mounted volume so loads and settings survive a rebuild.
RUN useradd --create-home --uid 10001 bot \
 && mkdir -p /data \
 && chown -R bot:bot /data /app
USER bot

CMD ["python", "bot.py"]

# ------------------------------------------------------------------- test
# Built only on demand: docker compose run --rm tests
FROM runtime AS test

USER root
RUN pip install --no-cache-dir pytest pytest-asyncio
COPY pytest.ini ./
COPY tests ./tests
USER bot

ENV DB_PATH=/tmp/rcbot-test.db \
    TELEGRAM_BOT_TOKEN=test \
    ANTHROPIC_API_KEY=test \
    ADMIN_TELEGRAM_ID=999

CMD ["python", "-m", "pytest", "tests/", "-q"]

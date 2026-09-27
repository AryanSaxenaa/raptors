FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    DOGFOOD_DEV_TOKENS=1 \
    DOGFOOD_DB=/data/dogfood.sqlite3

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fixtures.json run.py spec.md ./
COPY src ./src

RUN mkdir -p /data var && python -m dogfood init

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8080/api/health | grep -q '"ok":true'

CMD ["python", "-m", "dogfood", "serve"]

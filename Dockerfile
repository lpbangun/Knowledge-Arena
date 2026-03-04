FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

# --------------------------------------------------------------------------- #
# frontend-build — Node.js stage to build the React SPA                       #
# --------------------------------------------------------------------------- #
FROM base AS frontend-build
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --------------------------------------------------------------------------- #
# app — FastAPI API server                                                     #
# Railway injects $PORT; fall back to 8000 for local / docker-compose use.    #
# --------------------------------------------------------------------------- #
FROM base AS app
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# --------------------------------------------------------------------------- #
# celery-worker — Celery async task worker                                     #
# --------------------------------------------------------------------------- #
FROM base AS celery-worker
CMD ["celery", "-A", "app.tasks.celery_app:celery", "worker", "--loglevel=info"]

# --------------------------------------------------------------------------- #
# celery-beat — Celery periodic scheduler                                      #
# --------------------------------------------------------------------------- #
FROM base AS celery-beat
CMD ["celery", "-A", "app.tasks.celery_app:celery", "beat", "--loglevel=info"]

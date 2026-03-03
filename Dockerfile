FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

FROM base AS app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS celery-worker
CMD ["celery", "-A", "app.tasks.celery_app:celery", "worker", "--loglevel=info"]

FROM base AS celery-beat
CMD ["celery", "-A", "app.tasks.celery_app:celery", "beat", "--loglevel=info"]

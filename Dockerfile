FROM python:3.12-slim AS base

# Install system dependencies for python-magic, Pillow, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

# ── API target ──────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "agentic_fs.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Worker target ───────────────────────────────────────────
FROM base AS worker
CMD ["celery", "-A", "agentic_fs.worker.celery_app", "worker", "--loglevel=info", "--concurrency=2"]

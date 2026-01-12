# syntax=docker/dockerfile:1.7

# ----------------------------
# Base deps layer (no source code)
# ----------------------------
FROM python:3.11-slim AS deps

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps needed for Python packages (psycopg2 etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install base Python deps
COPY requirements.base.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.base.txt

# ----------------------------
# App source layer (shared)
# ----------------------------
FROM deps AS app

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy source code last (better cache)
COPY --chown=appuser:appuser . .

USER appuser

# ----------------------------
# API / Orchestrator
# ----------------------------
FROM app AS orchestrator
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ----------------------------
# Worker deps (extends base deps + ML system libs + worker pip deps)
# ----------------------------
FROM deps AS worker_deps

# Additional system dependencies for ML/OCR
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.worker.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.worker.txt

# ----------------------------
# Worker runtime
# ----------------------------
FROM worker_deps AS worker

RUN useradd -m -u 1000 appuser

WORKDIR /app
COPY --chown=appuser:appuser . .

RUN mkdir -p /app/storage && chown -R appuser:appuser /app/storage

USER appuser
CMD ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info", "--concurrency=4"]

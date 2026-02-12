# syntax=docker/dockerfile:1.7

# ----------------------------
# Base deps layer (no source code)
# ----------------------------
# base image update for new dependencies 3.11 to 3.13
FROM python:3.13-slim AS deps

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps needed for Python packages (psycopg2 etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (needed for WhatsApp bot service)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Pre-install WhatsApp dependencies globally to avoid runtime installation issues
RUN npm config set cache /tmp/.npm && \
    npm install -g @whiskeysockets/baileys@^6.0.0 @hapi/boom@^10.0.0 qrcode@^1.5.0 pino@^9.0.0

# Pre-install MathJax v4 renderer worker dependencies
COPY tools/mathjax_renderer_v4/package*.json /tmp/mathjax_renderer_v4/
RUN cd /tmp/mathjax_renderer_v4 && npm ci --omit=dev

# Install base Python deps added binary version for psycopg2 to avoid build issues
RUN pip install --only-binary=:all: psycopg2-binary==2.9.11 
COPY requirements.base.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.base.txt
RUN pip install tiktoken>=0.5.0 filetype>=1.2.0

# ----------------------------
# App source layer (shared)
# ----------------------------
FROM deps AS app

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy source code last (better cache)
COPY --chown=appuser:appuser . .

# Install local Node deps for MathJax worker in final image.
RUN cd /app/tools/mathjax_renderer_v4 && npm ci --omit=dev

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

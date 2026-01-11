# Docker Infrastructure Guide

## Overview

The application uses a **multi-stage Docker setup** optimized for both development and production environments.

### Architecture

- **Orchestrator (API)**: Lean image (~200MB) without ML dependencies
- **Worker**: Heavy image (~900MB) with pix2text, torch, and ML libraries
- **PostgreSQL**: Database with health checks
- **Redis**: Message broker with health checks
- **Qdrant**: Vector database

## Running the Application

### Development Mode (Fast Iteration)

```bash
# Build and start with hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# View logs
docker compose logs -f orchestrator worker
```

**Features**:
- Code mounted as volumes (changes reflected immediately)
- `--reload` enabled for uvicorn
- Running as root for convenience
- Writable filesystems

### Production Mode (Full Security)

```bash
# Build and start in production mode
docker compose -f docker-compose.yml up -d --build

# View logs
docker compose logs -f
```

**Features**:
- Read-only root filesystems
- Non-root user (UID 1000)
- No privilege escalation
- Health checks and graceful shutdowns
- Log rotation (10MB × 3 files)
- Restart policies

## Configuration

### Environment Variables

Create a `.env` file in the project root (see `.env.example`):

```bash
OPENAI_API_KEY=your_key_here
JWT_SECRET_KEY=your_strong_random_secret
CORS_ALLOWED_ORIGINS=http://localhost:3000
USE_JSON_LOGGING=true
```

### Health Checks

- **Orchestrator**: `GET /health` responds with 200 OK
- **PostgreSQL**: `pg_isready` check every 10s
- **Redis**: `redis-cli ping` check every 10s

## Build Optimization

### Multi-Stage Dockerfile

The Dockerfile uses separate targets:
- `base`: Common dependencies (FastAPI, SQLModel, etc.)
- `orchestrator`: Lean API image
- `worker`: Heavy ML/OCR image

### BuildKit Cache

Dependencies are cached using `--mount=type=cache`, eliminating redundant downloads:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.base.txt
```

### Split Requirements

- `requirements.base.txt`: Core API dependencies (~150MB)
- `requirements.worker.txt`: ML/OCR dependencies (~750MB)

## Security Features

| Feature | Implementation |
|---------|---------------|
| Read-only filesystem | `read_only: true` (with `/tmp` tmpfs) |
| Non-root user | `user: "1000:1000"` |
| No privilege escalation | `security_opt: no-new-privileges:true` |
| Log rotation | `max-size: 10m`, `max-file: 3` |
| Graceful shutdown | `stop_grace_period: 30s` (API), `60s` (worker) |
| Health dependencies | `depends_on: condition: service_healthy` |

## Troubleshooting

### Rebuild from scratch

```bash
docker compose down -v  # Warning: deletes volumes
docker compose -f docker-compose.yml up -d --build
```

### Check container logs

```bash
docker compose logs orchestrator --tail 50
docker compose logs worker --tail 50
```

### Verify health status

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Production Deployment Checklist

- [ ] Set strong `JWT_SECRET_KEY` in `.env`
- [ ] Configure production `CORS_ALLOWED_ORIGINS`
- [ ] Enable `USE_JSON_LOGGING=true`
- [ ] Run database migrations: `docker compose exec orchestrator alembic upgrade head`
- [ ] Verify health checks are passing
- [ ] Set up external monitoring for `/health` endpoint
- [ ] Configure log aggregation (e.g., ELK stack)
- [ ] Scale workers based on load: `docker compose up -d --scale worker=3`

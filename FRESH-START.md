# UAsk Application - Fresh Start Guide

## Quick Start (Automated)

Run this single command to set up everything:

```powershell
.\fresh-start.ps1
```

This script will:
1. ✅ Create .env file (if missing)
2. ✅ Clean Docker environment
3. ✅ Build and start all containers
4. ✅ Run database migrations
5. ✅ Seed admin user
6. ✅ Seed system prompts
7. ✅ Verify health

## Manual Setup (Step-by-Step)

### 1. Create .env File

Create a `.env` file in the project root with these values:

```bash
# REQUIRED: Your OpenAI API Key
OPENAI_API_KEY=sk-your-actual-key-here

# REQUIRED: Generate strong random string
JWT_SECRET_KEY=your-very-long-random-secret-at-least-32-chars

# Frontend CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Logging (false for dev, true for prod)
USE_JSON_LOGGING=false

# Database (must match docker-compose.yml)
POSTGRES_USER=uask_user
POSTGRES_PASSWORD=uask_password
POSTGRES_DB=uask_db
DATABASE_URL=postgresql://uask_user:uask_password@postgres:5432/uask_db

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_URL=http://qdrant:6333

# Storage
LOCAL_STORAGE_PATH=/app/storage
```

### 2. Clean Docker (if needed)

```powershell
docker compose down -v
```

### 3. Start Services

```powershell
# Development mode (with hot-reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# OR Production mode
docker compose -f docker-compose.yml up -d --build
```

### 4. Wait for Services

Wait ~30 seconds for PostgreSQL, Redis, and Qdrant to be healthy.

### 5. Run Database Migrations

```powershell
docker compose exec orchestrator alembic upgrade head
```

### 6. Seed Admin User

```powershell
docker compose exec orchestrator python seed_admin.py
```

**Admin Credentials**:
- Email: `loai@uask.ai`
- Password: `ssLr1980`

### 7. Seed System Prompts

```powershell
docker compose exec orchestrator python seed_prompts.py
```

### 8. Verify Everything Works

```powershell
# Check backend health
curl http://localhost:8000/health

# Check API docs
start http://localhost:8000/docs

# Check frontend
start http://localhost:3000
```

## Application URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Main application UI |
| Backend API | http://localhost:8000 | FastAPI backend |
| API Docs | http://localhost:8000/docs | Interactive Swagger docs |
| PostgreSQL | localhost:5432 | Database (user: uask_user) |
| Redis | localhost:6379 | Message broker |
| Qdrant | localhost:6333 | Vector database |

## Default Accounts

### Admin Account
- **Email**: loai@uask.ai
- **Password**: ssLr1980
- **Role**: admin
- **Tier**: enterprise
- **Quotas**: Unlimited

## Troubleshooting

### Containers won't start

```powershell
# Check logs
docker compose logs orchestrator
docker compose logs worker

# Restart individual service
docker compose restart orchestrator
```

### Database connection errors

```powershell
# Check postgres health
docker compose exec postgres pg_isready -U uask_user

# Verify migration status
docker compose exec orchestrator alembic current
```

### "Module not found" errors

```powershell
# Rebuild containers
docker compose down
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### Can't login as admin

```powershell
# Re-run admin seeding
docker compose exec orchestrator python seed_admin.py
```

## Development Workflow

### View logs in real-time

```powershell
docker compose logs -f orchestrator worker
```

### Restart after code changes

Development mode has hot-reload, but for major changes:

```powershell
docker compose restart orchestrator worker
```

### Access database directly

```powershell
docker compose exec postgres psql -U uask_user -d uask_db
```

### Run Python scripts in container

```powershell
docker compose exec orchestrator python your_script.py
```

## Clean Restart

To start completely fresh (⚠️ deletes all data):

```powershell
docker compose down -v
.\fresh-start.ps1
```

## Production Deployment

For production, use the production compose file without dev overrides:

```powershell
docker compose -f docker-compose.yml up -d --build
```

Make sure to:
- Set `USE_JSON_LOGGING=true` in .env
- Use a strong `JWT_SECRET_KEY`
- Restrict `CORS_ALLOWED_ORIGINS` to your domain
- Enable HTTPS/TLS
- Set up external monitoring for `/health` endpoint

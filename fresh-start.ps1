#!/usr/bin/env pwsh
# Fresh Start Setup Script for UAsk Application
# This script sets up everything needed for a clean start
#Requires -Version 7.0
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8 # Enable UTF-8 output for emojis @luai this is needed not all CLI support UTF-8 by default
# for this part first:
# winget search --id Microsoft.PowerShell
# winget install --id Microsoft.PowerShell --source winget
# then add it as default powershell in terminal settings in VScode

Write-Host "🚀 UAsk Application - Fresh Start Setup" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if .env exists
Write-Host "📋 Step 1: Checking environment configuration..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Write-Host "❌ .env file not found!" -ForegroundColor Red
    Write-Host "Creating .env file with template..." -ForegroundColor Yellow
    
    $envContent = @'
# CRITICAL: Replace these values with your actual credentials

# OpenAI API Key (REQUIRED)
OPENAI_API_KEY=your_actual_openai_api_key_here

# JWT Secret (Generate: openssl rand -hex 32)
JWT_SECRET_KEY=c30b3b96cfd63513ad517d60ecdde8ecf69ac4cc8e389f3b85d29884c0150245

# CORS Allowed Origins
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Logging
USE_JSON_LOGGING=false

# Database (matches docker-compose.yml)
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
'@
    
    Set-Content -Path ".env" -Value $envContent
    Write-Host "✅ Created .env file" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env and add your actual OPENAI_API_KEY!" -ForegroundColor Red
    Write-Host "⚠️  Also update JWT_SECRET_KEY with a strong random value!" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter after you've updated .env with your credentials"
}
else {
    Write-Host "✅ .env file exists" -ForegroundColor Green
}

# Step 2: Stop and clean Docker
Write-Host ""
Write-Host "🧹 Step 2: Cleaning Docker environment..." -ForegroundColor Yellow
docker compose down -v 2>$null
Write-Host "✅ Docker cleaned" -ForegroundColor Green

# Step 3: Build and start containers
Write-Host ""
Write-Host "🏗️  Step 3: Building and starting containers (this may take 5-15 minutes)..." -ForegroundColor Yellow
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Containers built and started" -ForegroundColor Green
}
else {
    Write-Host "❌ Failed to build containers" -ForegroundColor Red
    exit 1
}

# Step 4: Wait for services to be healthy
Write-Host ""
Write-Host "⏳ Step 4: Waiting for services to be ready (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 36

# Step 5: Run database migrations
Write-Host ""
Write-Host "📊 Step 5: Running database migrations..." -ForegroundColor Yellow
docker compose exec -T orchestrator alembic upgrade head

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Database migrations completed" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Migrations may have failed - continuing..." -ForegroundColor Yellow
}

# Step 6: Seed admin user
Write-Host ""
Write-Host "👤 Step 6: Creating admin user..." -ForegroundColor Yellow
docker compose exec -T orchestrator python seed_admin.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Admin user seeded" -ForegroundColor Green
    Write-Host "   Email: loai@uask.ai" -ForegroundColor Cyan
    Write-Host "   Password: ssLr1980" -ForegroundColor Cyan
}
else {
    Write-Host "⚠️  Admin seeding may have failed" -ForegroundColor Yellow
}

# Step 7: Seed prompts
Write-Host ""
Write-Host "📝 Step 7: Seeding system prompts..." -ForegroundColor Yellow
docker compose exec -T orchestrator python seed_prompts.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ System prompts seeded" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Prompt seeding may have failed" -ForegroundColor Yellow
}

# Step 8: Verify health
Write-Host ""
Write-Host "🏥 Step 8: Verifying application health..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

$health = curl -s http://localhost:8000/health 2>$null
if ($health) {
    Write-Host "✅ Backend is healthy: $health" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Backend health check failed" -ForegroundColor Yellow
}

# Final summary
Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "✨ Setup Complete!" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📌 Quick Start:" -ForegroundColor Yellow
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "👤 Admin Credentials:" -ForegroundColor Yellow
Write-Host "   Email:    loai@uask.ai" -ForegroundColor Cyan
Write-Host "   Password: ssLr1980" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔍 Useful Commands:" -ForegroundColor Yellow
Write-Host "   View logs:    docker compose logs -f" -ForegroundColor Cyan
Write-Host "   Stop:         docker compose down" -ForegroundColor Cyan
Write-Host "   Restart:      docker compose restart" -ForegroundColor Cyan
Write-Host ""

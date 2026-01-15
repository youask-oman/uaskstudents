# Student Seeding & Testing Guide

## Overview
This document describes the tools created for seeding 420 production-quality student accounts and verifying the "School Directory + Location-Aware Profile" features under live traffic conditions.

## 1. Database Seeding (`seed_students.py`)
Located at: `backend/app/scripts/seed_students.py`

### Features
- Creates **420 students** (IDs 100-519).
- Password: `password123` (hashed with PBKDF2).
- **Realistic Profiles**:
    - Names: Real firstname/lastname combinations.
    - Locations: 60% USA (50 states), 40% Canada (13 provinces/territories).
    - Grades: Grade 1 to Grade 12.
    - Tier: `enterprise`.
- **Verification**: Includes built-in tests to verify DB state.

### Usage
Run inside the orchestrator container:

```bash
# Preview (Dry Run)
docker exec uask_orchestrator python -m app.scripts.seed_students --dry-run

# Commit & Verify (Recommended)
docker exec uask_orchestrator python -m app.scripts.seed_students --commit --force --test
```

## 2. Live Traffic Testing (`test_live_traffic.py`)
Located at: `backend/app/scripts/test_live_traffic.py`

### Features
- **End-to-End Test**: Logs in as seeded students and hits the API.
- **Context Verification**: Ensures the API injects the correct Location/Grade context into the Solver V3.
- **Cache Verification**: Submits duplicate problems to verify cache hits (latency reduction).
- **Stability Check**: Runs a sequence of requests to ensure no crashes (500s) or connection drops.

### Usage
Run inside the orchestrator container (requires orchestration to be running):

```bash
docker exec uask_orchestrator python -m app.scripts.test_live_traffic
```

### Expected Output
```
✅ Profile loaded: [Name] | [Country] | [Province]
✅ Success (Cold: 25s)
✅ Latency reduced (Warm: 0.5s)
✅ LIVE TRAFFIC TEST PASSED - ZERO ERRORS
```

## 3. Key Fixes Implemented
During the development of these tools, several bugs in the main application were identified and fixed:
1. **API Schema**: Updated `UserProfileResponse` to return `profile_country`, `profile_province_state`, and `grade_level`.
2. **Solver V3**: Fixed `AttributeError` caused by incorrect initialization order of `_fallback_model`.
3. **Validation**: Updated test payloads to comply with strict `validate_math_query` and `text_query` schema requirements.

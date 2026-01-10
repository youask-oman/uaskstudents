from fastapi import FastAPI
from app.database import create_db_and_tables

app = FastAPI(title="UAsk.ai Orchestrator")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

from app.api import api_router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"status": "ok", "service": "UAsk.ai Orchestrator v1"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}

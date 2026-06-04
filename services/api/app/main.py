"""
AegisStream API Service
FastAPI backend for the AegisStream reliability observatory.
"""
import sys
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from services.api.app.database import init_db
from services.api.app.routes.events import router as events_router
from services.api.app.routes.metrics import router as metrics_router
from services.api.app.routes.deployment import reviews_router, deployment_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AegisStream API",
    description="Real-Time Behavioral Evaluation and Reliability Observatory for Open-Source LLMs",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)
app.include_router(metrics_router)
app.include_router(reviews_router)
app.include_router(deployment_router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "aegisstream-api"}


@app.get("/", tags=["system"])
def root():
    return {
        "service": "AegisStream API",
        "version": "1.0.0",
        "docs": "/docs",
    }

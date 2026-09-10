import os
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.database.session import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logging.getLogger(__name__).info("Application started, database initialized")
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Database initialization skipped (Postgres unavailable: %s). Operating in fallback mode.",
            exc,
        )
    yield


app = FastAPI(
    title="Intelligent Caching Optimization Middleware for AI Agents",
    description="Multi-level caching middleware with exact, semantic, context, and tool caches",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, tags=["cache"])

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@app.get("/")
async def root():
    return {"message": "Intelligent Cache Middleware", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

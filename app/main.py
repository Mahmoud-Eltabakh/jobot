"""Main FastAPI application entry point for Jobot."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging

logger = logging.getLogger("jobot.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    import os
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting %s v0.1.0 in %s mode", settings.app_name, settings.env)
    
    # Initialize SQLite database schema and seed default settings
    from app.db.database import init_db
    init_db()
    
    # Do NOT start background loops when running under automated test suite
    is_testing = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("JOBOT_TESTING"))

    scheduler = None
    queue_worker = None

    if not is_testing:
        # Start background scheduler
        from app.scrapers.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()

        # Start background continuous task queue worker
        from app.queue.worker import get_queue_worker
        queue_worker = get_queue_worker()
        queue_worker.start()
    
    yield
    if queue_worker:
        queue_worker.stop()
    if scheduler:
        scheduler.shutdown()
    logger.info("Shutting down %s", settings.app_name)


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Intelligent AI Job Search & Tracking Agent",
    lifespan=lifespan,
    debug=settings.debug,
)

# Include API & Web Routers
from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.profile import router as profile_router
from app.api.queue import router as queue_router
from app.api.scrapers import router as scrapers_router
from app.api.settings import router as settings_router
from app.web.routes import router as web_router

app.include_router(applications_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(queue_router)
app.include_router(scrapers_router)
app.include_router(settings_router)
app.include_router(web_router)

# CORS configuration - restrict to local origins by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint returning system status."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
    }

"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.migrations import run_migrations
from app.db.pool import close_db, init_db
from app.routers import analysis, analytics, health, scraping
from app.scheduler.jobs import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    setup_logging()
    logger.info("Starting Instagram Campaign API")

    # Database
    await init_db()
    await run_migrations()

    # Scheduler
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Instagram Campaign Analytics API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
origins = settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(scraping.router)
app.include_router(analysis.router)
app.include_router(analytics.router)

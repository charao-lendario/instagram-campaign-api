"""FastAPI application entry point.

Configures CORS, structured logging, lifespan events (including APScheduler),
and router registration.

Story 1.7 AC1: APScheduler lifecycle tied to FastAPI lifespan.
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.routers import analysis, analytics, health, scraping, suggestions
from app.scheduler.jobs import shutdown_scheduler, start_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown hooks.

    AC1: Starts APScheduler on startup and shuts it down on exit.
    """
    setup_logging()
    logger.info("Application starting up")
    start_scheduler()
    yield
    shutdown_scheduler()
    logger.info("Application shutting down")


app = FastAPI(
    title="Instagram Campaign Analytics API",
    description="Backend para scraping e analise de comentarios do Instagram para campanhas politicas",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
_raw_origins = settings.ALLOWED_ORIGINS.strip()
if _raw_origins == "*":
    _allowed_origins: list[str] = ["*"]
else:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Router Registration
# ---------------------------------------------------------------------------
app.include_router(health.router, tags=["Health"])
app.include_router(scraping.router, prefix="/api/v1/scraping", tags=["Scraping"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(suggestions.router, prefix="/api/v1/analytics", tags=["Suggestions"])

"""APScheduler job definitions and scheduler management.

Story 1.7 AC1: Initializes BackgroundScheduler with IntervalTrigger,
adds the run_full_pipeline job, and provides start/shutdown/status helpers
for the FastAPI lifespan.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.services.pipeline import run_full_pipeline

logger = logging.getLogger(__name__)

# Module-level scheduler instance (singleton)
scheduler = BackgroundScheduler()


def _pipeline_job() -> None:
    """Wrapper that APScheduler calls on each interval tick."""
    run_full_pipeline(trigger="scheduler")


def start_scheduler() -> None:
    """Configure and start the background scheduler.

    AC1: Adds the run_full_pipeline job with IntervalTrigger using
    SCRAPING_INTERVAL_HOURS from settings.
    """
    scheduler.add_job(
        _pipeline_job,
        IntervalTrigger(hours=settings.SCRAPING_INTERVAL_HOURS),
        id="full_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "scheduler_started",
        extra={
            "interval_hours": settings.SCRAPING_INTERVAL_HOURS,
        },
    )


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully.

    AC1d: Called during FastAPI lifespan cleanup.
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")


def is_scheduler_running() -> bool:
    """Check if the scheduler is currently running."""
    return scheduler.running

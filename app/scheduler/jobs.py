"""APScheduler configuration for periodic scraping."""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core.logging import logger
from app.services.scraping import run_full_pipeline

scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """Initialize and start the APScheduler."""
    global scheduler
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _run_pipeline_job,
        "interval",
        hours=settings.SCRAPING_INTERVAL_HOURS,
        id="scraping_pipeline",
        name="Instagram Scraping Pipeline",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started: pipeline every {settings.SCRAPING_INTERVAL_HOURS}h"
    )


def stop_scheduler() -> None:
    """Shutdown the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def _run_pipeline_job() -> None:
    """Job wrapper for the scraping pipeline."""
    logger.info("Scheduled pipeline job triggered")
    try:
        await run_full_pipeline()
    except RuntimeError as e:
        logger.warning(f"Scheduled pipeline skipped: {e}")
    except Exception as e:
        logger.error(f"Scheduled pipeline error: {e}")

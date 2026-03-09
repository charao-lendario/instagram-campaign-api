"""Health check endpoint."""

from fastapi import APIRouter

from app.core.logging import logger
from app.db.pool import get_pool
from app.services.scraping import get_last_scrape_info

router = APIRouter()


@router.get("/health")
async def health_check():
    # Check database
    db_status = "disconnected"
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "connected"
    except Exception as e:
        logger.error(f"Health check DB error: {e}")

    # Check scheduler
    from app.scheduler.jobs import scheduler
    scheduler_status = "running" if scheduler and scheduler.running else "stopped"

    # Last scrape
    last_scrape = None
    try:
        last_scrape = await get_last_scrape_info()
    except Exception:
        pass

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "scheduler": scheduler_status,
        "last_scrape": last_scrape,
    }

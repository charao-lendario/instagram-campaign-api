"""Health check endpoint.

Returns service status including database connectivity, scheduler state,
and last scrape timestamp.
"""

import logging

from fastapi import APIRouter

from app.db.supabase import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str | None]:
    """Return health status including real Supabase connectivity test.

    Performs a lightweight ``SELECT id FROM candidates LIMIT 1`` to verify
    database connectivity.
    """
    db_status = "disconnected"

    try:
        client = get_supabase()
        result = client.table("candidates").select("id").limit(1).execute()
        if result is not None:
            db_status = "connected"
    except Exception:
        logger.warning("Health check: Supabase connection failed", exc_info=True)

    return {
        "status": "ok",
        "database": db_status,
        "scheduler": "stopped",
        "last_scrape": None,
    }

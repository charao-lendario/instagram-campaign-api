"""Health check endpoint.

Returns service status including database connectivity, scheduler state,
and last scrape timestamp.

Story 1.7 AC5: Full health check with scheduler status and last_scrape.
"""

import logging
from typing import Any

from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.db.supabase import get_supabase
from app.scheduler.jobs import is_scheduler_running

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> Any:
    """Return health status including real Supabase connectivity test,
    scheduler state, and last successful scrape timestamp.

    AC5: Returns 200 OK when healthy, 503 when database is down.
    """
    db_status = "disconnected"
    last_scrape: str | None = None

    try:
        client = get_supabase()
        result = client.table("candidates").select("id").limit(1).execute()
        if result is not None:
            db_status = "connected"

        # Get last successful scrape via PL/pgSQL function
        scrape_result = client.rpc("get_last_successful_scrape", {}).execute()
        if scrape_result.data is not None:
            raw = scrape_result.data
            if isinstance(raw, str) and raw:
                last_scrape = raw
            elif isinstance(raw, list) and raw and raw[0]:
                last_scrape = str(raw[0])

    except Exception:
        logger.warning("Health check: Supabase connection failed", exc_info=True)

    scheduler_status = "running" if is_scheduler_running() else "stopped"

    payload: dict[str, str | None] = {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "scheduler": scheduler_status,
        "last_scrape": last_scrape,
    }

    if db_status != "connected":
        return JSONResponse(status_code=503, content=payload)

    return payload

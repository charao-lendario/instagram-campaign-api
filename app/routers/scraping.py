"""Scraping endpoints."""

import asyncio

from fastapi import APIRouter, HTTPException

from app.core.logging import logger
from app.services.scraping import is_pipeline_running, run_full_pipeline

router = APIRouter(prefix="/api/v1/scraping", tags=["scraping"])


@router.post("/run")
async def trigger_scraping():
    """Trigger a full scraping + analysis pipeline."""
    if await is_pipeline_running():
        raise HTTPException(status_code=409, detail="Pipeline already running")

    # Run pipeline in background
    async def _run():
        try:
            await run_full_pipeline()
        except Exception as e:
            logger.error(f"Background pipeline error: {e}")

    asyncio.create_task(_run())

    return {
        "status": "started",
        "message": "Scraping pipeline started in background",
    }

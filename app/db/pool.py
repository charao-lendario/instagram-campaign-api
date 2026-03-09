import asyncpg

from app.core.config import settings
from app.core.logging import logger

pool: asyncpg.Pool | None = None


async def init_db() -> None:
    global pool
    logger.info("Initializing database connection pool")
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=10,
    )
    logger.info("Database pool created successfully")


async def close_db() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None
        logger.info("Database pool closed")


async def get_pool() -> asyncpg.Pool:
    assert pool is not None, "Database pool not initialized. Call init_db() first."
    return pool

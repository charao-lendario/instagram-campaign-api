import os
from pathlib import Path

from app.core.logging import logger
from app.db.pool import get_pool

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


async def run_migrations() -> None:
    """Run all SQL migration files in order, tracking which have been applied."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Create migrations tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Get already applied migrations
        applied = {
            row["filename"]
            for row in await conn.fetch("SELECT filename FROM _migrations")
        }

        # Find and sort migration files
        migration_files = sorted(
            f for f in os.listdir(MIGRATIONS_DIR)
            if f.endswith(".sql")
        )

        for filename in migration_files:
            if filename in applied:
                logger.debug(f"Migration {filename} already applied, skipping")
                continue

            filepath = MIGRATIONS_DIR / filename
            sql = filepath.read_text(encoding="utf-8")

            logger.info(f"Applying migration: {filename}")
            try:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _migrations (filename) VALUES ($1)",
                    filename,
                )
                logger.info(f"Migration {filename} applied successfully")
            except Exception as e:
                logger.error(f"Migration {filename} failed: {e}")
                raise

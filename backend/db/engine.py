from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.config import settings

engine: AsyncEngine = create_async_engine(
    settings.postgres_dsn,
    echo=False,
    pool_size=10,
    max_overflow=5,
)


async def check_db() -> bool:
    """Return True if database is reachable."""
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    return True

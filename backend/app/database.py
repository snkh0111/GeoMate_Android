"""SQLAlchemy async engine and session factory."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},  # SQLite needs this for async
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base — all models inherit from this."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables and run dev migrations. Called at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Dev migrations: add columns that may be missing from older DBs
        await _run_dev_migrations(conn)


async def _run_dev_migrations(conn):
    """Apply lightweight dev migrations for SQLite.

    For production, use Alembic. These are for development convenience.
    """
    from sqlalchemy import text

    migrations = [
        # Document parser fields (added after initial documents table)
        "ALTER TABLE documents ADD COLUMN parsed_content JSON",
        "ALTER TABLE documents ADD COLUMN parsed_at DATETIME",
    ]

    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass  # Column already exists — skip

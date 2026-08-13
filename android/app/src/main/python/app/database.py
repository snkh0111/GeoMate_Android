"""SQLAlchemy engine and session factory (synchronous).

Uses the synchronous SQLAlchemy API so it does not depend on the
``greenlet`` C extension, which has no Android wheel (Chaquopy can
only install wheels). FastAPI runs synchronous endpoints in a thread
pool, so blocking SQLite access is fine for a single-user local app.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},  # SQLite across threads
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base — all models inherit from this."""
    pass


def get_db():
    """FastAPI dependency: yields a synchronous database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Create all tables and run dev migrations. Called at application startup."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        _run_dev_migrations(conn)


def _run_dev_migrations(conn):
    """Apply lightweight dev migrations for SQLite.

    For production, use Alembic. These are for development convenience.
    """
    from sqlalchemy import text

    migrations = [
        # Document parser fields (added after initial documents table)
        "ALTER TABLE documents ADD COLUMN parsed_content JSON",
        "ALTER TABLE documents ADD COLUMN parsed_at DATETIME",
        # Source-document tracking for cascade deletion of generated routes/plans
        "ALTER TABLE field_routes ADD COLUMN source_document_id INTEGER",
        "ALTER TABLE study_plans ADD COLUMN source_document_id INTEGER",
        "ALTER TABLE knowledge_documents ADD COLUMN source_document_id INTEGER",
    ]

    for sql in migrations:
        try:
            conn.execute(text(sql))
        except Exception:
            pass  # Column already exists — skip

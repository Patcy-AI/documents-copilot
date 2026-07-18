"""Async database engine and session for request-path code.

Alembic owns schema (sync, psycopg); this module owns runtime queries (async,
asyncpg). asyncpg is used for the async engine because — unlike psycopg's async
mode — it runs on any event loop, including Windows' default ProactorEventLoop,
so ``uvicorn app.main:app`` works unchanged on Windows and Linux.

The backend connects as the ``postgres`` role over the direct Supabase
connection, which **bypasses Row-Level Security**. Ownership must therefore be
enforced in application code (see ``app.database.chats.get_owned_thread``), not
by RLS.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


def _async_database_url() -> str:
    """DATABASE_URL on the asyncpg driver."""
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Supabase requires TLS; ssl="require" encrypts without local CA verification,
# avoiding cert-chain friction on the direct connection.
engine = create_async_engine(
    _async_database_url(),
    connect_args={"ssl": "require"},
    pool_pre_ping=True,
)

# expire_on_commit=False so ORM objects stay usable after commit (e.g. reading
# a thread's id/timestamps to serialize a response).
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, commit on success, roll back on error.

    Not for use inside a StreamingResponse body — the dependency's session closes
    when the response starts streaming. Streaming routes open their own session
    via ``SessionLocal`` instead.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

"""Async SQLAlchemy engine + session factory.

The schema is owned by db/init.sql (brief §7); we do not call create_all() in
production paths.

Vector handling: we rely on pgvector's SQLAlchemy `Vector` type for ORM inserts
(it serializes embeddings to the pgvector text literal, which Postgres casts on
the way in) and on explicit `(:param)::vector` casts in the raw similarity
queries. That keeps everything as text-in / text-out and avoids installing the
asyncpg binary vector codec, which would otherwise clash with the text literals
the ORM type produces for vector-typed parameters.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a database session."""
    async with async_session_factory() as session:
        yield session

"""Test fixtures.

Tests need a real Postgres+pgvector (the matching path is exercised for real,
not mocked). Point them at one via TEST_DATABASE_URL; otherwise they use the
app's configured DATABASE_URL. The intended way to run them is inside the
backend container, where `db` is reachable and the pgvector extension exists:

    docker compose up -d db backend
    docker compose exec backend pytest -q

Schema is created with SQLAlchemy metadata here (tests only) — production uses
db/init.sql. App tables are truncated before each test for isolation.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

# Redirect the app + tests at the test database *before* app modules import
# settings (which reads DATABASE_URL at import time).
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import async_session_factory, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.pipeline import pipeline  # noqa: E402

_CAMERA_SEED = """
    INSERT INTO cameras (name, location, source_type)
    SELECT * FROM (VALUES
        ('Checkpoint A', 'Main Terminal - Entry Gate', 'upload'),
        ('Checkpoint B', 'Bus Bay 3 - Departures',    'upload')
    ) AS s(name, location, source_type)
    WHERE NOT EXISTS (SELECT 1 FROM cameras)
"""


@pytest_asyncio.fixture(scope="session")
async def _schema():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(_CAMERA_SEED))
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def clean_db(_schema):
    # Reset per-test state: DB tables (keep seeded cameras) and pipeline cooldown.
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE persons, refs, alerts, audit_log RESTART IDENTITY CASCADE")
        )
    pipeline._cooldown.clear()
    yield


@pytest_asyncio.fixture
async def session(clean_db):
    async with async_session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(clean_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

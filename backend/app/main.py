"""FastAPI application: CORS, static file serving, routes, and the alerts WS."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routes import alerts, cameras, enroll, persons, process, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("lfr")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Ensure runtime image directories exist before serving them.
    for sub in ("references", "alerts"):
        Path(settings.data_dir, sub).mkdir(parents=True, exist_ok=True)
    logger.info("LFR backend started. DATA_DIR=%s", settings.data_dir)
    yield


app = FastAPI(title="LFR Prototype", version="0.1.0", lifespan=lifespan)

# CORS. Auth would plug in here (e.g. JWT middleware); MVP uses a single
# hardcoded "officer" identity, so no auth layer yet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(persons.router)
app.include_router(enroll.router)
app.include_router(process.router)
app.include_router(alerts.router)
app.include_router(cameras.router)
app.include_router(ws.router)


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve reference crops and alert captures by URL (brief §9.7). Mounted after
# routes so it never shadows the API. The directory is created in lifespan.
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
app.mount("/data", StaticFiles(directory=settings.data_dir), name="data")

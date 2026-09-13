"""WebSocket connection manager: tracks connected dashboard clients and
broadcasts alert / heartbeat messages to all of them.

A single module-level instance (`manager`) is shared across routes and the
pipeline so an alert emitted deep in video processing reaches every dashboard.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("lfr.ws")


class WebSocketManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        logger.info("WS client connected (%d total)", len(self._clients))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
        logger.info("WS client disconnected (%d total)", len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all clients, dropping any that error out."""
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - a broken socket must not stop the rest
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)
            logger.info("Pruned %d dead WS client(s)", len(dead))

    @property
    def client_count(self) -> int:
        return len(self._clients)


manager = WebSocketManager()

"""WebSocket endpoint for live alerts.

Clients connect to /ws/alerts and receive:
  * {"type": "alert", "alert": AlertOut}  when a match is confirmed
  * {"type": "heartbeat"}                 every ~20s to keep the link alive

The server tolerates disconnects; the frontend handles reconnection.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..ws_manager import manager

router = APIRouter()

HEARTBEAT_SECONDS = 20


@router.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            # We don't expect inbound messages, but receiving keeps the
            # connection state accurate and detects client disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        await manager.disconnect(websocket)


async def _heartbeat(websocket: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await websocket.send_json({"type": "heartbeat"})
    except Exception:  # noqa: BLE001 - socket closed; the main loop cleans up
        return

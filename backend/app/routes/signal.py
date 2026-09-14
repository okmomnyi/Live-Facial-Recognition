"""WebRTC signaling relay for the multi-camera Camera Wall.

Media (the actual video) is peer-to-peer between browsers and never touches the
backend. This endpoint only relays the small setup messages (SDP offers/answers
and ICE candidates) between peers in the same room, so it is very light.

Protocol (client <-> server), all JSON:
  connect:  WS /ws/signal?room=<id>&peer=<peerId>&role=<publisher|viewer>&name=<label>
  server -> newcomer:   {"type":"peers","peers":[{"peer_id","role","name"}, ...]}
  server -> others:     {"type":"peer-joined","peer":{"peer_id","role","name"}}
  client -> server:     {"type":"signal","to":<peerId>,"payload":<opaque>}
  server -> target:     {"type":"signal","from":<peerId>,"payload":<opaque>}
  server -> room:       {"type":"peer-left","peer_id":<id>}   (on disconnect)
  server -> peer:       {"type":"heartbeat"}                  (~20s keepalive)

Rooms live in memory only and are dropped when empty. No auth (matches the
prototype's single-officer model); a real deployment would authenticate here.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("lfr.signal")
router = APIRouter()

HEARTBEAT_SECONDS = 20


@dataclass
class Peer:
    peer_id: str
    role: str
    name: str
    ws: WebSocket


class SignalHub:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, Peer]] = {}
        self._lock = asyncio.Lock()

    async def join(self, room: str, peer: Peer) -> list[Peer]:
        """Add a peer; return the peers that were already in the room."""
        async with self._lock:
            members = self._rooms.setdefault(room, {})
            existing = [p for p in members.values() if p.peer_id != peer.peer_id]
            members[peer.peer_id] = peer
            return existing

    async def leave(self, room: str, peer_id: str) -> list[Peer]:
        """Remove a peer; return the remaining peers to notify."""
        async with self._lock:
            members = self._rooms.get(room)
            if not members:
                return []
            members.pop(peer_id, None)
            if not members:
                del self._rooms[room]
                return []
            return list(members.values())

    async def get(self, room: str, peer_id: str) -> Peer | None:
        async with self._lock:
            return (self._rooms.get(room) or {}).get(peer_id)


hub = SignalHub()


async def _send(peer: Peer, message: dict) -> None:
    with contextlib.suppress(Exception):
        await peer.ws.send_json(message)


@router.websocket("/ws/signal")
async def signal_ws(websocket: WebSocket) -> None:
    params = websocket.query_params
    room = params.get("room") or "default"
    peer_id = params.get("peer")
    role = params.get("role") or "viewer"
    name = params.get("name") or ""
    if not peer_id:
        await websocket.close(code=4000)
        return

    await websocket.accept()
    me = Peer(peer_id=peer_id, role=role, name=name, ws=websocket)
    existing = await hub.join(room, me)

    # Tell the newcomer who is already here, and announce the newcomer to them.
    await _send(me, {
        "type": "peers",
        "peers": [{"peer_id": p.peer_id, "role": p.role, "name": p.name} for p in existing],
    })
    joined_msg = {"type": "peer-joined",
                  "peer": {"peer_id": peer_id, "role": role, "name": name}}
    for p in existing:
        await _send(p, joined_msg)

    logger.info("signal join room=%s peer=%s role=%s (now %d)", room, peer_id, role, len(existing) + 1)
    heartbeat = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "signal":
                target_id = msg.get("to")
                target = await hub.get(room, target_id) if target_id else None
                if target is not None:
                    await _send(target, {
                        "type": "signal",
                        "from": peer_id,
                        "payload": msg.get("payload"),
                    })
            # any other message types are ignored (forward-compatible)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - malformed frame etc.; clean up below
        logger.info("signal error peer=%s: %s", peer_id, exc)
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
        remaining = await hub.leave(room, peer_id)
        for p in remaining:
            await _send(p, {"type": "peer-left", "peer_id": peer_id})
        logger.info("signal leave room=%s peer=%s", room, peer_id)


async def _heartbeat(websocket: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await websocket.send_json({"type": "heartbeat"})
    except Exception:  # noqa: BLE001 - socket closed; main loop cleans up
        return

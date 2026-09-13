"""The processing pipeline: frame -> detect -> quality gate -> embed -> search
watchlist -> (consensus) -> emit alert.

Two entry points:
  * process_image  - single still; a match emits an alert immediately.
  * process_video  - decodes every Nth frame, uses an IoU tracker + multi-frame
                     consensus, and emits alerts over the course of processing.

Alert emission (shared): crop the face, save a PNG, insert an `alerts` row,
broadcast over WebSocket, and write an audit_log entry. A per-(person, camera)
cooldown suppresses repeat alerts.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .audit import log_action
from .config import settings
from .face_service import DetectedFace, get_face_service
from .schemas import AlertOut
from .tracker import IoUTracker
from .ws_manager import manager

logger = logging.getLogger("lfr.pipeline")


@dataclass
class MatchCandidate:
    person_id: int
    person_name: str
    person_category: str
    ref_id: int
    ref_image_path: str
    similarity: float


def _vector_literal(embedding: np.ndarray) -> str:
    """pgvector text literal, e.g. '[0.1,0.2,...]'. Cast with ::vector in SQL."""
    return "[" + ",".join(f"{x:.7f}" for x in embedding.tolist()) + "]"


async def search_watchlist(
    session: AsyncSession, embedding: np.ndarray
) -> MatchCandidate | None:
    """Cosine-similarity search against refs. Returns the best candidate at or
    above MATCH_THRESHOLD, else None."""
    sql = text(
        """
        SELECT p.id AS person_id,
               p.name AS person_name,
               p.category AS person_category,
               r.id AS ref_id,
               r.image_path AS image_path,
               1 - (r.embedding <=> (:query)::vector) AS similarity
        FROM refs r
        JOIN persons p ON p.id = r.person_id
        ORDER BY r.embedding <=> (:query)::vector
        LIMIT 1
        """
    )
    row = (
        await session.execute(sql, {"query": _vector_literal(embedding)})
    ).first()
    if row is None:
        return None
    if row.similarity < settings.match_threshold:
        return None
    return MatchCandidate(
        person_id=row.person_id,
        person_name=row.person_name,
        person_category=row.person_category,
        ref_id=row.ref_id,
        ref_image_path=row.image_path,
        similarity=float(row.similarity),
    )


class Pipeline:
    def __init__(self) -> None:
        # (person_id, camera_id) -> last alert monotonic timestamp
        self._cooldown: dict[tuple[int, int | None], float] = {}

    def _in_cooldown(self, person_id: int, camera_id: int | None, now: float) -> bool:
        last = self._cooldown.get((person_id, camera_id))
        return last is not None and (now - last) < settings.alert_cooldown_seconds

    def _mark_alert(self, person_id: int, camera_id: int | None, now: float) -> None:
        self._cooldown[(person_id, camera_id)] = now

    async def _camera_name(
        self, session: AsyncSession, camera_id: int | None
    ) -> str | None:
        if camera_id is None:
            return None
        row = (
            await session.execute(
                text("SELECT name FROM cameras WHERE id = :id"), {"id": camera_id}
            )
        ).first()
        return row.name if row else None

    async def emit_alert(
        self,
        session: AsyncSession,
        *,
        candidate: MatchCandidate,
        face: DetectedFace,
        camera_id: int | None,
    ) -> AlertOut:
        """Persist + broadcast an alert for a confirmed match candidate."""
        alerts_dir = Path(settings.data_dir) / "alerts"
        alerts_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.png"
        disk_path = alerts_dir / filename
        cv2.imwrite(str(disk_path), face.crop_bgr)
        # Served path (matches the FastAPI static mount at /data).
        capture_path = f"{settings.data_dir}/alerts/{filename}"

        camera_name = await self._camera_name(session, camera_id)
        confidence = round(candidate.similarity, 4)

        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO alerts
                        (person_id, ref_id, camera_id, confidence, capture_path, status)
                    VALUES (:person_id, :ref_id, :camera_id, :confidence, :capture_path,
                            'pending')
                    RETURNING id, created_at
                    """
                ),
                {
                    "person_id": candidate.person_id,
                    "ref_id": candidate.ref_id,
                    "camera_id": camera_id,
                    "confidence": confidence,
                    "capture_path": capture_path,
                },
            )
        ).first()
        alert_id = row.id
        created_at = row.created_at

        await log_action(
            session,
            actor="system",
            action="alert_created",
            subject_type="alert",
            subject_id=alert_id,
            detail={
                "person_id": candidate.person_id,
                "confidence": confidence,
                "camera_id": camera_id,
            },
            commit=False,
        )
        await session.commit()

        alert = AlertOut(
            id=alert_id,
            person_id=candidate.person_id,
            person_name=candidate.person_name,
            person_category=candidate.person_category,
            ref_id=candidate.ref_id,
            ref_image_path=candidate.ref_image_path,
            camera_id=camera_id,
            camera_name=camera_name,
            confidence=confidence,
            capture_path=capture_path,
            status="pending",
            reviewed_by=None,
            reviewed_at=None,
            created_at=created_at,
        )
        await manager.broadcast(
            {"type": "alert", "alert": alert.model_dump(mode="json")}
        )
        logger.info(
            "ALERT person=%s conf=%.3f camera=%s -> id=%d",
            candidate.person_name,
            confidence,
            camera_id,
            alert_id,
        )
        return alert

    async def process_image(
        self, session: AsyncSession, image_bgr: np.ndarray, camera_id: int | None
    ) -> tuple[int, list[AlertOut], dict[str, int]]:
        """Process a single still. Each matched face emits an alert immediately
        (no consensus for a one-shot image). Returns
        (faces_detected, alerts, rejections)."""
        service = get_face_service()
        result = await asyncio.to_thread(service.analyze, image_bgr)
        now = time.monotonic()
        alerts: list[AlertOut] = []

        for face in result.faces:
            candidate = await search_watchlist(session, face.embedding)
            if candidate is None:
                continue
            if self._in_cooldown(candidate.person_id, camera_id, now):
                continue
            alert = await self.emit_alert(
                session, candidate=candidate, face=face, camera_id=camera_id
            )
            self._mark_alert(candidate.person_id, camera_id, now)
            alerts.append(alert)

        return len(result.faces), alerts, result.rejections

    async def process_video(
        self, session: AsyncSession, video_path: str, camera_id: int | None
    ) -> tuple[int, int, list[AlertOut], dict[str, int]]:
        """Process a video as a simulated live feed. Uses an IoU tracker and
        multi-frame consensus before emitting. Returns
        (frames_processed, faces_detected, alerts, rejections)."""
        service = get_face_service()
        tracker = IoUTracker(
            iou_threshold=0.3, max_age_seconds=settings.consensus_window_seconds
        )
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frames_processed = 0
        faces_detected = 0
        alerts: list[AlertOut] = []
        rejections: dict[str, int] = {}
        frame_idx = -1

        try:
            while True:
                ok = await asyncio.to_thread(cap.grab)
                if not ok:
                    break
                frame_idx += 1
                if frame_idx % settings.frame_skip != 0:
                    continue
                ok, frame = await asyncio.to_thread(cap.retrieve)
                if not ok or frame is None:
                    break

                # Simulated timeline based on the frame's position in the video,
                # so the consensus window reflects real elapsed video time.
                ts = frame_idx / fps
                frames_processed += 1

                result = await asyncio.to_thread(service.analyze, frame)
                faces_detected += len(result.faces)
                for reason, count in result.rejections.items():
                    rejections[reason] = rejections.get(reason, 0) + count

                boxes = [f.bbox for f in result.faces]
                tracks = tracker.update(boxes, ts)

                for face, track in zip(result.faces, tracks, strict=True):
                    candidate = await search_watchlist(session, face.embedding)
                    if candidate is None:
                        continue
                    track.record_match(ts, candidate.person_id, candidate.similarity)
                    consensus = track.consensus_person(
                        now=ts,
                        window_seconds=settings.consensus_window_seconds,
                        min_frames=settings.consensus_frames,
                    )
                    if consensus is None:
                        continue
                    person_id, _best_sim, _count = consensus
                    if person_id != candidate.person_id:
                        continue

                    now_mono = time.monotonic()
                    if self._in_cooldown(person_id, camera_id, now_mono):
                        track.alerted.add(person_id)
                        continue

                    alert = await self.emit_alert(
                        session, candidate=candidate, face=face, camera_id=camera_id
                    )
                    self._mark_alert(person_id, camera_id, now_mono)
                    track.alerted.add(person_id)
                    alerts.append(alert)
        finally:
            cap.release()

        return frames_processed, faces_detected, alerts, rejections


pipeline = Pipeline()

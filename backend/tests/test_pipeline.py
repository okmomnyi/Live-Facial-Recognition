"""Pipeline matching + alert-emission tests.

These exercise the real DB path (pgvector cosine search, alert insert, audit
log, WebSocket broadcast) with directly-inserted embeddings, so they run
deterministically without the face model. Real face detection is covered by the
gated tests in test_face_service.py and by scripts/smoke_face.py.
"""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import text

from app.config import settings
from app.face_service import DetectedFace
from app.models import Person, Ref
from app.pipeline import pipeline, search_watchlist


def _unit(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512).astype(np.float32)
    return v / np.linalg.norm(v)


async def _enroll(session, name: str, category: str, emb: np.ndarray) -> tuple[int, int]:
    person = Person(name=name, category=category)
    session.add(person)
    await session.flush()
    ref = Ref(
        person_id=person.id,
        image_path=f"/data/references/{name}.png",
        embedding=emb.tolist(),
        quality_score=0.9,
    )
    session.add(ref)
    await session.flush()
    await session.commit()
    return person.id, ref.id


def _fake_face(emb: np.ndarray) -> DetectedFace:
    return DetectedFace(
        bbox=(0, 0, 100, 100),
        width=100,
        height=100,
        det_score=0.9,
        blur_score=0.8,
        quality=0.85,
        embedding=emb,
        crop_bgr=np.zeros((100, 100, 3), dtype=np.uint8),
    )


@pytest.mark.asyncio
async def test_search_matches_enrolled_and_rejects_stranger(session):
    emb_a = _unit(1)
    emb_b = _unit(2)  # near-orthogonal to A in high dimensions
    await _enroll(session, "Person A", "wanted", emb_a)
    await _enroll(session, "Person B", "missing", emb_b)

    match = await search_watchlist(session, emb_a)
    assert match is not None
    assert match.person_name == "Person A"
    assert match.similarity >= settings.match_threshold
    assert match.similarity > 0.99  # identical vector

    # A random unrelated face should not match either enrolled person.
    stranger = _unit(999)
    assert await search_watchlist(session, stranger) is None


@pytest.mark.asyncio
async def test_emit_alert_creates_row_and_audit(session):
    emb_a = _unit(1)
    person_id, ref_id = await _enroll(session, "Person A", "wanted", emb_a)

    candidate = await search_watchlist(session, emb_a)
    assert candidate is not None

    alert = await pipeline.emit_alert(
        session, candidate=candidate, face=_fake_face(emb_a), camera_id=1
    )
    assert alert.status == "pending"
    assert alert.confidence >= settings.match_threshold
    assert alert.person_id == person_id
    assert alert.ref_id == ref_id

    count = (await session.execute(text("SELECT COUNT(*) FROM alerts"))).scalar_one()
    assert count == 1

    audit = (
        await session.execute(
            text("SELECT action FROM audit_log WHERE action = 'alert_created'")
        )
    ).all()
    assert len(audit) == 1


@pytest.mark.asyncio
async def test_process_image_emits_single_alert(session):
    # Full image path, but we monkeypatch face detection to return one known
    # face so the test is deterministic (no model). Everything downstream --
    # search, cooldown, emit, DB, audit -- is real.
    emb_a = _unit(1)
    await _enroll(session, "Person A", "wanted", emb_a)
    await _enroll(session, "Person B", "missing", _unit(2))

    from app import pipeline as pipeline_module

    class _StubService:
        def analyze(self, _img):
            from app.face_service import AnalysisResult

            return AnalysisResult(
                faces=[_fake_face(emb_a)], rejections={}, raw_detections=1
            )

    original = pipeline_module.get_face_service
    pipeline_module.get_face_service = lambda: _StubService()
    try:
        faces, alerts, rejections = await pipeline.process_image(
            session, np.zeros((200, 200, 3), dtype=np.uint8), camera_id=1
        )
    finally:
        pipeline_module.get_face_service = original

    assert faces == 1
    assert len(alerts) == 1
    assert alerts[0].person_name == "Person A"
    assert alerts[0].confidence >= settings.match_threshold

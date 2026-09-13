"""Endpoint smoke tests using httpx against the ASGI app.

These cover routing, validation, and DB-backed responses for every endpoint.
The happy-path enroll/process flows (which need the face model + real photos)
are covered by the gated tests in test_face_service.py; here we assert the
routes exist and validate input correctly without invoking the model.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cameras_seeded(client):
    r = await client.get("/api/cameras")
    assert r.status_code == 200
    cameras = r.json()
    assert len(cameras) >= 2
    assert {"id", "name", "location", "source_type"} <= cameras[0].keys()


@pytest.mark.asyncio
async def test_persons_empty(client):
    r = await client.get("/api/persons")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_missing_person_404(client):
    r = await client.get("/api/persons/12345")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_enroll_requires_image(client):
    # Missing the required `images` file -> 422 (no model invoked).
    r = await client.post(
        "/api/enroll", data={"name": "Nobody", "category": "poi"}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_enroll_bad_category(client):
    r = await client.post(
        "/api/enroll",
        data={"name": "X", "category": "not-a-category"},
        files={"images": ("a.png", b"not-an-image", "image/png")},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_process_image_unreadable_422(client):
    r = await client.post(
        "/api/process/image",
        files={"image": ("bad.png", b"not-an-image", "image/png")},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_alerts_list_empty_and_filter_validation(client):
    r = await client.get("/api/alerts")
    assert r.status_code == 200
    assert r.json() == []

    r = await client.get("/api/alerts", params={"status": "bogus"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_review_missing_alert_404(client):
    r = await client.post(
        "/api/alerts/999/review", json={"action": "confirm", "reviewer": "officer"}
    )
    assert r.status_code == 404

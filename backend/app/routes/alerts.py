"""Alert routes: list the queue/history and review (confirm/dismiss)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_action
from ..db import get_session
from ..schemas import AlertOut, ReviewRequest

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

_ALERT_SELECT = """
    SELECT a.id, a.person_id, p.name AS person_name, p.category AS person_category,
           a.ref_id, r.image_path AS ref_image_path,
           a.camera_id, c.name AS camera_name,
           a.confidence, a.capture_path, a.status,
           a.reviewed_by, a.reviewed_at, a.created_at
    FROM alerts a
    JOIN persons p ON p.id = a.person_id
    JOIN refs r    ON r.id = a.ref_id
    LEFT JOIN cameras c ON c.id = a.camera_id
"""


def _row_to_alert(row) -> AlertOut:
    return AlertOut(
        id=row.id,
        person_id=row.person_id,
        person_name=row.person_name,
        person_category=row.person_category,
        ref_id=row.ref_id,
        ref_image_path=row.ref_image_path,
        camera_id=row.camera_id,
        camera_name=row.camera_name,
        confidence=float(row.confidence),
        capture_path=row.capture_path,
        status=row.status,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
    )


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    status: str = Query("pending"),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[AlertOut]:
    allowed = {"pending", "confirmed", "dismissed", "all"}
    if status not in allowed:
        raise HTTPException(status_code=422, detail=f"status must be one of {allowed}")

    sql = _ALERT_SELECT
    params: dict = {"limit": limit}
    if status != "all":
        sql += " WHERE a.status = :status"
        params["status"] = status
    sql += " ORDER BY a.created_at DESC LIMIT :limit"

    rows = (await session.execute(text(sql), params)).all()
    return [_row_to_alert(r) for r in rows]


@router.post("/{alert_id}/review", response_model=AlertOut)
async def review_alert(
    alert_id: int,
    body: ReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    if body.action not in {"confirm", "dismiss"}:
        raise HTTPException(status_code=422, detail="action must be confirm or dismiss")
    new_status = "confirmed" if body.action == "confirm" else "dismissed"
    reviewed_at = datetime.now(timezone.utc)

    result = await session.execute(
        text(
            """
            UPDATE alerts
               SET status = :status, reviewed_by = :reviewer, reviewed_at = :reviewed_at
             WHERE id = :id
            RETURNING id
            """
        ),
        {
            "status": new_status,
            "reviewer": body.reviewer,
            "reviewed_at": reviewed_at,
            "id": alert_id,
        },
    )
    if result.first() is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    await log_action(
        session,
        actor=body.reviewer,
        action=f"alert_{new_status}",
        subject_type="alert",
        subject_id=alert_id,
        detail={"action": body.action},
        commit=False,
    )
    await session.commit()

    row = (
        await session.execute(
            text(_ALERT_SELECT + " WHERE a.id = :id"), {"id": alert_id}
        )
    ).first()
    return _row_to_alert(row)

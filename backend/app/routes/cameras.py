"""Camera routes: list, create, rename, and delete checkpoints.

Delete is FK-safe: alerts.camera_id references cameras(id) with no cascade, so a
camera that any alert points at cannot be removed (409 rather than a 500 from the
FK violation). Every mutating action is audit-logged.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_action
from ..db import get_session
from ..models import Alert, Camera
from ..schemas import CameraCreate, CameraOut, CameraUpdate

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


async def _get_or_404(session: AsyncSession, camera_id: int) -> Camera:
    camera = (
        await session.execute(select(Camera).where(Camera.id == camera_id))
    ).scalar_one_or_none()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    session: AsyncSession = Depends(get_session),
) -> list[CameraOut]:
    rows = (await session.execute(select(Camera).order_by(Camera.id))).scalars().all()
    return [CameraOut.model_validate(c) for c in rows]


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
async def create_camera(
    body: CameraCreate,
    session: AsyncSession = Depends(get_session),
) -> CameraOut:
    camera = Camera(
        name=body.name,
        location=body.location,
        source_type=body.source_type,
    )
    session.add(camera)
    await session.flush()
    await log_action(
        session,
        actor="officer",
        action="camera_created",
        subject_type="camera",
        subject_id=camera.id,
        detail={"name": camera.name, "source_type": camera.source_type},
        commit=False,
    )
    await session.commit()
    return CameraOut.model_validate(camera)


@router.patch("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    session: AsyncSession = Depends(get_session),
) -> CameraOut:
    camera = await _get_or_404(session, camera_id)
    changes: dict[str, str | None] = {}
    if body.name is not None:
        camera.name = body.name
        changes["name"] = body.name
    if body.location is not None:
        camera.location = body.location
        changes["location"] = body.location
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")

    await log_action(
        session,
        actor="officer",
        action="camera_updated",
        subject_type="camera",
        subject_id=camera.id,
        detail=changes,
        commit=False,
    )
    await session.commit()
    await session.refresh(camera)
    return CameraOut.model_validate(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await _get_or_404(session, camera_id)

    alert_count = (
        await session.execute(
            select(func.count(Alert.id)).where(Alert.camera_id == camera_id)
        )
    ).scalar_one()
    if alert_count > 0:
        raise HTTPException(
            status_code=409, detail="camera has alerts and can't be deleted"
        )

    await session.execute(delete(Camera).where(Camera.id == camera_id))
    await log_action(
        session,
        actor="officer",
        action="camera_deleted",
        subject_type="camera",
        subject_id=camera_id,
        detail={"deleted_at": datetime.now(timezone.utc).isoformat()},
        commit=False,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

"""Camera routes: list configured checkpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Camera
from ..schemas import CameraOut

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    session: AsyncSession = Depends(get_session),
) -> list[CameraOut]:
    rows = (await session.execute(select(Camera).order_by(Camera.id))).scalars().all()
    return [CameraOut.model_validate(c) for c in rows]

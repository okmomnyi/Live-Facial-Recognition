"""Processing routes: run the pipeline on an uploaded image or video.

Both emit alerts over WebSocket as matches are confirmed (see pipeline). The
video endpoint returns its summary only after processing completes; the live
view is the dashboard subscribed to /ws/alerts.
"""

from __future__ import annotations

import os
import tempfile

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..pipeline import pipeline
from ..schemas import ProcessResult

router = APIRouter(prefix="/api/process", tags=["process"])


@router.post("/image", response_model=ProcessResult)
async def process_image(
    image: UploadFile = File(...),
    camera_id: int | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> ProcessResult:
    raw = await image.read()
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=422, detail="Unreadable image")

    faces_detected, alerts, rejections = await pipeline.process_image(
        session, img, camera_id
    )
    return ProcessResult(
        frames_processed=1,
        faces_detected=faces_detected,
        matches=alerts,
        rejected=rejections,
    )


@router.post("/video", response_model=ProcessResult)
async def process_video(
    video: UploadFile = File(...),
    camera_id: int | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> ProcessResult:
    suffix = os.path.splitext(video.filename or "")[1] or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await video.read())
        tmp.flush()
        tmp.close()
        frames, faces, alerts, rejections = await pipeline.process_video(
            session, tmp.name, camera_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    return ProcessResult(
        frames_processed=frames,
        faces_detected=faces,
        matches=alerts,
        rejected=rejections,
    )

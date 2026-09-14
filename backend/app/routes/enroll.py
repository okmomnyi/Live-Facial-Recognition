"""Enrollment: create a person and attach reference photos + embeddings.

For each uploaded image we require exactly one face that passes the quality
gate; images with zero or multiple quality faces are skipped and reported in the
per-image status list (brief §9.2).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_action
from ..config import settings
from ..db import get_session
from ..face_service import get_face_service
from ..models import Person, Ref
from ..schemas import EnrollImageResult, EnrollResult, PersonOut

router = APIRouter(prefix="/api/enroll", tags=["enroll"])

_ALLOWED_CATEGORIES = {"wanted", "missing", "escaped", "poi"}


def _decode(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _padded_crop(
    img: np.ndarray, bbox: tuple[int, int, int, int], margin: float = 0.4
) -> np.ndarray:
    """Crop the face from the original image with margin around the bbox.

    A tight crop (no margin) can't be re-detected by SCRFD, so we save a padded
    crop as the reference image: it stays a good card thumbnail but also round-
    trips through detection if ever reprocessed. Does not affect the stored
    embedding, which is computed on the full image at enroll time.
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    mx = int((x2 - x1) * margin)
    my = int((y2 - y1) * margin)
    nx1, ny1 = max(0, x1 - mx), max(0, y1 - my)
    nx2, ny2 = min(w, x2 + mx), min(h, y2 + my)
    return img[ny1:ny2, nx1:nx2]


@router.post("", response_model=EnrollResult)
async def enroll(
    name: str = Form(...),
    category: str = Form(...),
    notes: str | None = Form(None),
    images: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
) -> EnrollResult:
    if category not in _ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"category must be one of {sorted(_ALLOWED_CATEGORIES)}",
        )
    if not images:
        raise HTTPException(status_code=422, detail="At least one image is required")

    service = get_face_service()
    references_dir = Path(settings.data_dir) / "references"
    references_dir.mkdir(parents=True, exist_ok=True)

    person = Person(name=name, category=category, notes=notes)
    session.add(person)
    await session.flush()  # assign person.id

    image_results: list[EnrollImageResult] = []
    for upload in images:
        raw = await upload.read()
        fname = upload.filename or "upload"
        img = _decode(raw)
        if img is None:
            image_results.append(
                EnrollImageResult(filename=fname, status="rejected", reason="unreadable")
            )
            continue

        result = service.analyze(img)
        if len(result.faces) == 0:
            image_results.append(
                EnrollImageResult(filename=fname, status="rejected", reason="no_face")
            )
            continue
        if len(result.faces) > 1:
            image_results.append(
                EnrollImageResult(
                    filename=fname, status="rejected", reason="multiple_faces"
                )
            )
            continue

        face = result.faces[0]
        out_name = f"{uuid.uuid4().hex}.png"
        # Save a padded crop (re-detectable) rather than the tight quality-gate
        # crop; the embedding is already computed on the full image.
        cv2.imwrite(str(references_dir / out_name), _padded_crop(img, face.bbox))
        image_path = f"{settings.data_dir}/references/{out_name}"

        ref = Ref(
            person_id=person.id,
            image_path=image_path,
            embedding=face.embedding.tolist(),
            quality_score=round(face.quality, 4),
        )
        session.add(ref)
        await session.flush()
        image_results.append(
            EnrollImageResult(
                filename=fname,
                status="ok",
                ref_id=ref.id,
                quality=round(face.quality, 4),
            )
        )

    ok_count = sum(1 for r in image_results if r.status == "ok")
    await log_action(
        session,
        actor="officer",
        action="person_enrolled",
        subject_type="person",
        subject_id=person.id,
        detail={
            "name": name,
            "category": category,
            "images_ok": ok_count,
            "images_total": len(image_results),
        },
        commit=False,
    )
    await session.commit()

    # Refresh ref_count + first-ref thumbnail for the response.
    ref_count = (
        await session.execute(
            select(func.count(Ref.id)).where(Ref.person_id == person.id)
        )
    ).scalar_one()
    thumbnail_path = (
        await session.execute(
            select(Ref.image_path)
            .where(Ref.person_id == person.id)
            .order_by(Ref.id)
            .limit(1)
        )
    ).scalar_one_or_none()

    person_out = PersonOut(
        id=person.id,
        name=person.name,
        category=person.category,
        notes=person.notes,
        created_at=person.created_at,
        ref_count=ref_count,
        thumbnail_path=thumbnail_path,
    )
    return EnrollResult(person=person_out, images=image_results)

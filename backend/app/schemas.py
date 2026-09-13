"""Pydantic response/request models (API contract, brief §9)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Category = Literal["wanted", "missing", "escaped", "poi"]


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Category
    notes: str | None = None
    created_at: datetime
    ref_count: int = 0
    # image_path of the person's first reference photo (for watchlist card
    # thumbnails), served by the /data static mount; null if none enrolled.
    thumbnail_path: str | None = None


class RefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    image_path: str
    quality_score: float
    created_at: datetime


class EnrollImageResult(BaseModel):
    filename: str
    status: Literal["ok", "rejected"]
    ref_id: int | None = None
    quality: float | None = None
    reason: str | None = None


class EnrollResult(BaseModel):
    person: PersonOut
    images: list[EnrollImageResult]


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None = None
    source_type: str


class CameraCreate(BaseModel):
    name: str
    location: str | None = None
    source_type: str = "upload"


class CameraUpdate(BaseModel):
    name: str | None = None
    location: str | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    person_name: str
    person_category: Category
    ref_id: int
    ref_image_path: str
    camera_id: int | None = None
    camera_name: str | None = None
    confidence: float
    capture_path: str
    status: Literal["pending", "confirmed", "dismissed"]
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class ProcessResult(BaseModel):
    frames_processed: int
    faces_detected: int
    matches: list[AlertOut]
    # Diagnostics so the pipeline "fails visibly": counts of rejected faces by reason.
    rejected: dict[str, int] = {}


class ReviewRequest(BaseModel):
    action: Literal["confirm", "dismiss"]
    reviewer: str = "officer"

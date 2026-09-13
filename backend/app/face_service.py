"""InsightFace wrapper: detection, quality gating, and embedding.

Uses the `buffalo_sc` model pack (SCRFD-500MF detector + MobileFaceNet
recognizer) via ONNX Runtime on CPU. Models auto-download to ~/.insightface on
first use (persisted as a Docker volume). The service is a lazy singleton so the
~30 MB model load happens once, on first request, not at import time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from .config import settings

logger = logging.getLogger("lfr.face")

# Blur normalization constant (variance-of-Laplacian scale). See brief §6.2.
_BLUR_SCALE = 300.0


@dataclass
class DetectedFace:
    """A single detected face with its quality metrics and embedding."""

    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    width: int
    height: int
    det_score: float
    blur_score: float
    quality: float
    embedding: np.ndarray  # (512,) float32, L2-normalized
    crop_bgr: np.ndarray  # BGR crop for saving/display


@dataclass
class AnalysisResult:
    """Outcome of analyzing one image/frame."""

    faces: list[DetectedFace]  # passed the quality gate
    rejections: dict[str, int]  # reason -> count (fail-visibly diagnostics)
    raw_detections: int  # total faces detected before gating


def variance_of_laplacian(gray: np.ndarray) -> float:
    """Focus measure: higher = sharper. Used for the blur gate."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


class FaceService:
    """Lazy singleton around InsightFace FaceAnalysis."""

    _instance: "FaceService | None" = None

    def __init__(self) -> None:
        self._app = None  # loaded on first analyze()

    @classmethod
    def instance(cls) -> "FaceService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._app is not None:
            return
        # Imported lazily so importing this module (e.g. in tests that mock it)
        # doesn't pull in the whole onnxruntime stack until actually needed.
        from insightface.app import FaceAnalysis

        logger.info("Loading InsightFace buffalo_sc (CPU)...")
        app = FaceAnalysis(
            name="buffalo_sc",
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        self._app = app
        logger.info("InsightFace ready.")

    def analyze(self, image_bgr: np.ndarray) -> AnalysisResult:
        """Detect faces, apply the quality gate, and compute embeddings.

        Returns accepted faces plus a per-reason rejection tally.
        """
        self._ensure_loaded()
        assert self._app is not None

        faces_raw = self._app.get(image_bgr)
        accepted: list[DetectedFace] = []
        rejections: dict[str, int] = {}
        h_img, w_img = image_bgr.shape[:2]

        def reject(reason: str) -> None:
            rejections[reason] = rejections.get(reason, 0) + 1

        for f in faces_raw:
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            # Clamp to image bounds.
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            w = x2 - x1
            h = y2 - y1
            if w <= 0 or h <= 0:
                reject("empty_bbox")
                continue

            det_score = float(getattr(f, "det_score", 0.0))
            if det_score < settings.det_threshold:
                reject("low_det_score")
                continue
            if w < settings.min_face_size or h < settings.min_face_size:
                reject("too_small")
                continue

            crop = image_bgr[y1:y2, x1:x2]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            blur_score = min(1.0, variance_of_laplacian(gray) / _BLUR_SCALE)
            if blur_score < settings.blur_reject_below:
                reject("too_blurry")
                continue

            embedding = getattr(f, "normed_embedding", None)
            if embedding is None:
                reject("no_embedding")
                continue
            embedding = np.asarray(embedding, dtype=np.float32)

            quality = (
                0.4 * det_score
                + 0.3 * min(1.0, min(w, h) / 200.0)
                + 0.3 * blur_score
            )

            accepted.append(
                DetectedFace(
                    bbox=(x1, y1, x2, y2),
                    width=w,
                    height=h,
                    det_score=det_score,
                    blur_score=blur_score,
                    quality=float(quality),
                    embedding=embedding,
                    crop_bgr=crop.copy(),
                )
            )

        return AnalysisResult(
            faces=accepted,
            rejections=rejections,
            raw_detections=len(faces_raw),
        )


def get_face_service() -> FaceService:
    return FaceService.instance()

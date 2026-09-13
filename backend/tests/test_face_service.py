"""Face service tests.

Pure-function tests (blur measure) always run. Tests that need the InsightFace
model download are gated behind RUN_MODEL_TESTS=1; a real-face detection test is
gated behind SAMPLE_FACE pointing at a consented photo. This keeps `pytest -q`
green offline while still allowing the full real-inference checks the brief wants
(see also scripts/smoke_face.py).
"""

from __future__ import annotations

import os

import cv2
import numpy as np
import pytest

from app.face_service import get_face_service, variance_of_laplacian

RUN_MODEL = os.environ.get("RUN_MODEL_TESTS") == "1"
SAMPLE_FACE = os.environ.get("SAMPLE_FACE")


def test_variance_of_laplacian_discriminates_blur():
    # A sharp high-frequency checkerboard has much higher Laplacian variance
    # than its blurred version -> the blur gate can tell them apart.
    board = np.zeros((200, 200), dtype=np.uint8)
    board[::2, ::2] = 255
    board[1::2, 1::2] = 255
    blurred = cv2.GaussianBlur(board, (11, 11), 0)

    sharp_var = variance_of_laplacian(board)
    blurred_var = variance_of_laplacian(blurred)

    assert sharp_var > blurred_var
    assert blurred_var / sharp_var < 0.5


@pytest.mark.skipif(not RUN_MODEL, reason="set RUN_MODEL_TESTS=1 to run model inference")
def test_model_runs_on_blank_image():
    # Real ONNX inference must run without error; a blank image yields no faces.
    service = get_face_service()
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    result = service.analyze(blank)
    assert result.raw_detections == 0
    assert result.faces == []


@pytest.mark.skipif(
    not (RUN_MODEL and SAMPLE_FACE and os.path.exists(SAMPLE_FACE or "")),
    reason="set RUN_MODEL_TESTS=1 and SAMPLE_FACE=<consented photo> to run",
)
def test_detects_real_face_and_gates_small_crop():
    service = get_face_service()
    img = cv2.imread(SAMPLE_FACE)
    assert img is not None
    result = service.analyze(img)
    assert len(result.faces) >= 1
    face = result.faces[0]
    # Embedding is 512-d and L2-normalized.
    assert face.embedding.shape[0] == 512
    assert abs(float(np.linalg.norm(face.embedding)) - 1.0) < 1e-2

    # A tiny downscaled crop is rejected by the min-size gate.
    small = cv2.resize(img, (40, 40))
    small_result = service.analyze(small)
    assert all(f.width >= 80 and f.height >= 80 for f in small_result.faces)

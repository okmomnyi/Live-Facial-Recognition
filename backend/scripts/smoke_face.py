"""Smoke test: confirm InsightFace downloads and runs inference on CPU.

Usage:
    python -m scripts.smoke_face [path/to/image.jpg]

With no argument it runs inference on a synthetic image (which detects 0 faces
but still proves the model loaded and ran). Pass a real, consented photo to see
a non-zero detection count and quality metrics.
"""

from __future__ import annotations

import sys

import cv2
import numpy as np

# Allow running as `python scripts/smoke_face.py` from the backend dir too.
sys.path.insert(0, ".")

from app.face_service import get_face_service  # noqa: E402


def load_image(path: str | None) -> np.ndarray:
    if path:
        img = cv2.imread(path)
        if img is None:
            raise SystemExit(f"Could not read image: {path}")
        return img
    # Synthetic fallback: a gradient with noise. No real face -> 0 detections.
    print("No image path given; using a synthetic image (expect 0 faces).")
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    for y in range(480):
        img[y, :, :] = int(255 * y / 480)
    noise = np.random.randint(0, 40, img.shape, dtype=np.uint8)
    return cv2.add(img, noise)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    image = load_image(path)

    print("Loading model (first run downloads ~30 MB to ~/.insightface)...")
    service = get_face_service()
    result = service.analyze(image)

    print(f"Raw detections:      {result.raw_detections}")
    print(f"Passed quality gate: {len(result.faces)}")
    if result.rejections:
        print(f"Rejections:          {result.rejections}")
    for i, face in enumerate(result.faces):
        print(
            f"  face[{i}] bbox={face.bbox} det={face.det_score:.3f} "
            f"blur={face.blur_score:.3f} quality={face.quality:.3f} "
            f"emb_dim={face.embedding.shape[0]} "
            f"emb_norm={float(np.linalg.norm(face.embedding)):.3f}"
        )
    print("OK: model loaded and inference ran.")


if __name__ == "__main__":
    main()

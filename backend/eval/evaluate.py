#!/usr/bin/env python3
"""Evaluation harness for the face-matching pipeline (brief §12.2).

Sweeps the cosine-similarity threshold and reports precision, recall, FAR
(false accept rate) and FRR (false reject rate), plus the best-F1 threshold. If
the manifest carries a `skin_tone` column, it also reports FAR/FRR per bin — the
groundwork for a bias audit.

Two modes:

  Real images (needs the InsightFace models + a manifest of image pairs):
      python eval/evaluate.py --manifest pairs/manifest.csv

  Self-test (no images, no models — fabricates separable synthetic embeddings
  just to prove the sweep/metrics wiring runs end to end):
      python eval/evaluate.py --self-test

Manifest format (CSV with a header):

    img_a,img_b,label,skin_tone
    same/alice_1.jpg,same/alice_2.jpg,same,III
    diff/alice_1.jpg,diff/bob_1.jpg,diff,III

`label` is `same` (both images are the same person) or `diff`. Paths are
resolved relative to the manifest file's directory. `skin_tone` is optional
(any binning scheme, e.g. Fitzpatrick I–VI).
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Thresholds swept, inclusive, per brief §12.2.
THRESHOLDS = np.round(np.arange(0.20, 0.7001, 0.02), 4)


@dataclass
class Pair:
    label: str  # 'same' | 'diff'
    similarity: float
    skin_tone: str | None = None


# --------------------------------------------------------------------------
# Embedding extraction (real mode)
# --------------------------------------------------------------------------


def _load_backend():
    """Put the backend package on sys.path and return the face service factory."""
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from app.face_service import get_face_service  # noqa: WPS433 (local import by design)

    return get_face_service()


def embedding_for(service, image_path: Path) -> np.ndarray | None:
    """Return the L2-normalized embedding of the highest-quality face, or None."""
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        print(f"  ! could not read {image_path}", file=sys.stderr)
        return None
    result = service.analyze(img)
    if not result.faces:
        print(f"  ! no usable face in {image_path}", file=sys.stderr)
        return None
    best = max(result.faces, key=lambda f: f.quality)
    return np.asarray(best.embedding, dtype=np.float32)


def pairs_from_manifest(manifest_path: Path) -> list[Pair]:
    service = _load_backend()
    base = manifest_path.parent
    cache: dict[str, np.ndarray | None] = {}

    def emb(rel: str) -> np.ndarray | None:
        if rel not in cache:
            cache[rel] = embedding_for(service, base / rel)
        return cache[rel]

    pairs: list[Pair] = []
    with manifest_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            label = (row.get("label") or "").strip().lower()
            if label not in ("same", "diff"):
                print(f"  ! row {i}: bad label {label!r}, skipping", file=sys.stderr)
                continue
            a, b = emb(row["img_a"].strip()), emb(row["img_b"].strip())
            if a is None or b is None:
                continue
            sim = float(np.dot(a, b))  # embeddings are L2-normalized -> cosine
            pairs.append(Pair(label=label, similarity=sim, skin_tone=(row.get("skin_tone") or "").strip() or None))
    return pairs


# --------------------------------------------------------------------------
# Self-test (synthetic embeddings, no images/models)
# --------------------------------------------------------------------------


def synthetic_pairs(n: int = 60, seed: int = 7) -> list[Pair]:
    """Fabricate separable pairs so the metrics/sweep code can be exercised
    without any real data. NOT a benchmark — purely a wiring test."""
    rng = np.random.default_rng(seed)
    dim = 512
    tones = ["I", "II", "III", "IV", "V", "VI"]
    pairs: list[Pair] = []

    def norm(v: np.ndarray) -> np.ndarray:
        return v / (np.linalg.norm(v) + 1e-9)

    for k in range(n):
        tone = tones[k % len(tones)]
        base = norm(rng.standard_normal(dim))
        # same person: base + small noise -> high similarity. In 512-d the noise
        # vector has norm ~sqrt(512), so the coefficient must be tiny (~0.03) to
        # keep cosine high (lands ~0.8); a larger value would swamp the base.
        same = norm(base + 0.03 * rng.standard_normal(dim))
        pairs.append(Pair("same", float(np.dot(base, same)), tone))
        # different person: mostly independent -> low similarity
        other = norm(rng.standard_normal(dim))
        pairs.append(Pair("diff", float(np.dot(base, other)), tone))
    return pairs


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


@dataclass
class Metrics:
    threshold: float
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def far(self) -> float:  # false accept rate: diff pairs wrongly accepted
        return self.fp / (self.fp + self.tn) if (self.fp + self.tn) else 0.0

    @property
    def frr(self) -> float:  # false reject rate: same pairs wrongly rejected
        return self.fn / (self.fn + self.tp) if (self.fn + self.tp) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def confusion(pairs: list[Pair], threshold: float) -> Metrics:
    tp = fp = tn = fn = 0
    for pr in pairs:
        predicted_same = pr.similarity >= threshold
        if pr.label == "same":
            tp += predicted_same
            fn += not predicted_same
        else:
            fp += predicted_same
            tn += not predicted_same
    return Metrics(threshold, tp, fp, tn, fn)


def sweep(pairs: list[Pair]) -> list[Metrics]:
    return [confusion(pairs, float(t)) for t in THRESHOLDS]


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def print_sweep(rows: list[Metrics]) -> Metrics:
    print(f"\n{'thr':>5}  {'prec':>6}  {'recall':>6}  {'FAR':>6}  {'FRR':>6}  {'F1':>6}")
    print("-" * 45)
    best = max(rows, key=lambda m: m.f1)
    for m in rows:
        marker = "  <- best F1" if m is best else ""
        print(
            f"{m.threshold:5.2f}  {m.precision:6.3f}  {m.recall:6.3f}  "
            f"{m.far:6.3f}  {m.frr:6.3f}  {m.f1:6.3f}{marker}"
        )
    print(
        f"\nBest F1 = {best.f1:.3f} at threshold {best.threshold:.2f} "
        f"(precision {best.precision:.3f}, recall {best.recall:.3f}, "
        f"FAR {best.far:.3f}, FRR {best.frr:.3f})"
    )
    return best


def print_bias_audit(pairs: list[Pair], threshold: float) -> None:
    binned: dict[str, list[Pair]] = {}
    for pr in pairs:
        if pr.skin_tone:
            binned.setdefault(pr.skin_tone, []).append(pr)
    if not binned:
        print("\n(no skin_tone column -> skipping per-bin bias audit)")
        return
    print(f"\nPer-bin FAR/FRR at threshold {threshold:.2f} (bias audit):")
    print(f"{'bin':>6}  {'n':>4}  {'FAR':>6}  {'FRR':>6}")
    print("-" * 28)
    for tone in sorted(binned):
        m = confusion(binned[tone], threshold)
        print(f"{tone:>6}  {len(binned[tone]):4d}  {m.far:6.3f}  {m.frr:6.3f}")
    print(
        "\nNote: large FAR/FRR gaps across bins indicate demographic bias. Bins "
        "need enough pairs each to be meaningful; treat tiny bins with caution."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Face-matching threshold sweep / bias audit.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest", type=Path, help="CSV manifest of image pairs")
    src.add_argument(
        "--self-test",
        action="store_true",
        help="Run on synthetic embeddings (no images/models) to verify the harness",
    )
    args = ap.parse_args()

    if args.self_test:
        print("Running SELF-TEST on synthetic embeddings (not a real benchmark).")
        pairs = synthetic_pairs()
    else:
        if not args.manifest.exists():
            print(f"Manifest not found: {args.manifest}", file=sys.stderr)
            return 2
        print(f"Loading pairs from {args.manifest} ...")
        pairs = pairs_from_manifest(args.manifest)

    n_same = sum(p.label == "same" for p in pairs)
    n_diff = sum(p.label == "diff" for p in pairs)
    print(f"Evaluated {len(pairs)} pairs ({n_same} same, {n_diff} diff).")
    if not pairs:
        print("No usable pairs — nothing to evaluate.", file=sys.stderr)
        return 1

    rows = sweep(pairs)
    best = print_sweep(rows)
    print_bias_audit(pairs, best.threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""A lightweight IoU tracker used for multi-frame consensus (brief §6.4).

The goal is not robust MOT — just enough temporal association so that repeated
matches of the same person to the same face across processed frames can be
required before an alert fires. Each track accumulates timestamped match
records; the pipeline queries `consensus_person` to decide when to emit.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Intersection-over-union of two (x1, y1, x2, y2) boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    bbox: tuple[int, int, int, int]
    last_update: float
    # (timestamp, person_id, similarity)
    matches: list[tuple[float, int, float]] = field(default_factory=list)
    # persons already alerted on this track (avoid re-alerting the same track)
    alerted: set[int] = field(default_factory=set)

    def record_match(self, ts: float, person_id: int, similarity: float) -> None:
        self.matches.append((ts, person_id, similarity))

    def consensus_person(
        self, now: float, window_seconds: float, min_frames: int
    ) -> tuple[int, float, int] | None:
        """Return (person_id, best_similarity, count) for a person matched at
        least `min_frames` times within the trailing window, else None. If
        multiple qualify, the one with the most matches (then highest sim) wins.
        """
        cutoff = now - window_seconds
        tally: dict[int, list[float]] = {}
        for ts, pid, sim in self.matches:
            if ts >= cutoff:
                tally.setdefault(pid, []).append(sim)

        best: tuple[int, float, int] | None = None
        for pid, sims in tally.items():
            if pid in self.alerted:
                continue
            count = len(sims)
            if count < min_frames:
                continue
            best_sim = max(sims)
            if best is None or (count, best_sim) > (best[2], best[1]):
                best = (pid, best_sim, count)
        return best


class IoUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_age_seconds: float = 5.0) -> None:
        self.iou_threshold = iou_threshold
        self.max_age_seconds = max_age_seconds
        self._tracks: list[Track] = []
        self._next_id = 1

    def update(
        self, boxes: list[tuple[int, int, int, int]], now: float
    ) -> list[Track]:
        """Associate each incoming box with a track (creating new ones as
        needed). Returns the Track objects aligned to the input `boxes` order.
        """
        self._prune(now)
        assigned: list[Track | None] = [None] * len(boxes)
        used_track_ids: set[int] = set()

        # Greedy: for each box, pick the best-IoU unused track over threshold.
        for i, box in enumerate(boxes):
            best_track: Track | None = None
            best_iou = self.iou_threshold
            for track in self._tracks:
                if track.id in used_track_ids:
                    continue
                score = iou(box, track.bbox)
                if score >= best_iou:
                    best_iou = score
                    best_track = track
            if best_track is not None:
                best_track.bbox = box
                best_track.last_update = now
                used_track_ids.add(best_track.id)
                assigned[i] = best_track

        # Unmatched boxes become new tracks.
        for i, box in enumerate(boxes):
            if assigned[i] is None:
                track = Track(id=self._next_id, bbox=box, last_update=now)
                self._next_id += 1
                self._tracks.append(track)
                assigned[i] = track

        return [t for t in assigned if t is not None]

    def _prune(self, now: float) -> None:
        self._tracks = [
            t for t in self._tracks if now - t.last_update <= self.max_age_seconds
        ]

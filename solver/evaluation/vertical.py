"""跨层对齐评价。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate


def compute_vertical_metrics(candidate: LayoutCandidate) -> dict[str, float]:
    stair = 1.0
    wet = 1.0

    if len(candidate.floors) >= 2:
        ref = candidate.floors[0]
        for fl in candidate.floors[1:]:
            if ref.stair_x0 is not None and fl.stair_x0 is not None:
                if abs(fl.stair_x0 - ref.stair_x0) > 0.01 or abs(fl.stair_x1 - ref.stair_x1) > 0.01:
                    stair = 0.0
            if ref.wet_zone_x0 is not None and fl.wet_zone_x0 is not None:
                if abs(fl.wet_zone_x0 - ref.wet_zone_x0) > 0.01 or abs(fl.wet_zone_x1 - ref.wet_zone_x1) > 0.01:
                    wet = 0.0

    return {"stair_alignment": stair, "wet_zone_alignment": wet}


def vertical_score(metrics: dict[str, float]) -> float:
    stair = metrics.get("stair_alignment", 1.0)
    wet = metrics.get("wet_zone_alignment", 1.0)
    return max(0.0, min(100.0, stair * 50 + wet * 50))

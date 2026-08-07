"""几何评价 metrics。"""

from __future__ import annotations

import math

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights
from solver.geometry.rect import from_placement


def compute_geometry_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, float]:
    w = program.buildable.width
    d = program.buildable.depth
    footprint = w * d
    ideal_perimeter = 4 * math.sqrt(footprint)
    actual_perimeter = 2 * (w + d)
    compactness = ideal_perimeter / actual_perimeter if actual_perimeter > 0 else 0.0

    area_errors: list[float] = []
    aspect_penalty = 0.0
    flagged_count = 0

    room_targets = {r.id: r.target_area for r in program.rooms}

    for fl in candidate.floors:
        for p in fl.placements:
            if p.category == RoomCategory.CIRCULATION.value or p.source.value == "generated":
                if p.room_id.startswith("stair"):
                    continue
            actual = p.rect.area
            target = room_targets.get(p.room_id)
            if target:
                area_errors.append(abs(actual - target) / target)
            ratio = p.aspect_ratio
            if ratio > weights.aspect_ratio_threshold:
                flagged_count += 1
                aspect_penalty += (ratio - weights.aspect_ratio_threshold) * 10

    area_accuracy = 1.0 - (sum(area_errors) / len(area_errors) if area_errors else 0.0)
    area_accuracy = max(0.0, min(1.0, area_accuracy))

    return {
        "area_accuracy": round(area_accuracy, 4),
        "aspect_ratio_penalty": round(aspect_penalty, 4),
        "compactness": round(compactness, 4),
        "perimeter_efficiency_pct": round(compactness * 100, 2),
        "slender_room_count": float(flagged_count),
    }


def geometry_score(metrics: dict[str, float]) -> float:
    base = (
        metrics.get("area_accuracy", 0) * 40
        + metrics.get("compactness", 0) * 40
        - metrics.get("aspect_ratio_penalty", 0)
    )
    return max(0.0, min(100.0, base))

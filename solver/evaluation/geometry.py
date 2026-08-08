"""几何评价 metrics。"""

from __future__ import annotations

import math

from packages.schema.layout import LayoutCandidate, PlacementSource, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights


def _is_program_room(placement: RoomPlacement) -> bool:
    """仅评价用户程序房间；跳过系统生成的 circulation。"""
    if placement.source == PlacementSource.GENERATED:
        return False
    if placement.category == RoomCategory.CIRCULATION.value:
        return False
    return True


def _proportional_area_accuracy(
    program: DesignProgram,
    placements: list[RoomPlacement],
) -> float:
    """
    Guillotine 按面积权重切分整层/分区，实际 m² 与 target_area 通常不一致。

    area_accuracy 衡量「面积份额」是否与目标权重一致：
    1 - TV(actual_share, target_share)
    其中 TV 为 total variation distance ∈ [0, 1]。
    """
    pairs: list[tuple[float, float]] = []
    for p in placements:
        if not _is_program_room(p):
            continue
        room = program.room_by_id(p.room_id)
        if room is None:
            continue
        pairs.append((p.rect.area, room.target_area))

    if not pairs:
        return 1.0

    actual_sum = sum(a for a, _ in pairs)
    target_sum = sum(t for _, t in pairs)
    if actual_sum <= 0 or target_sum <= 0:
        return 0.0

    tv = 0.0
    for actual, target in pairs:
        tv += abs(actual / actual_sum - target / target_sum)
    return max(0.0, min(1.0, 1.0 - tv / 2.0))


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

    aspect_penalty = 0.0
    flagged_count = 0
    floor_accuracies: list[float] = []

    for fl in candidate.floors:
        floor_accuracies.append(_proportional_area_accuracy(program, fl.placements))
        for p in fl.placements:
            if not _is_program_room(p):
                continue
            ratio = p.aspect_ratio
            if ratio > weights.aspect_ratio_threshold:
                flagged_count += 1
                aspect_penalty += (ratio - weights.aspect_ratio_threshold) * 10

    area_accuracy = (
        sum(floor_accuracies) / len(floor_accuracies) if floor_accuracies else 1.0
    )

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

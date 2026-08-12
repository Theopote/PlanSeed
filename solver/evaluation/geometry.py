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


def _occupied_footprint(candidate: LayoutCandidate) -> tuple[float, float] | None:
    """Largest per-floor AABB of program rooms (layout, not site)."""
    best: tuple[float, float, float] | None = None
    for fl in candidate.floors:
        rooms = [p for p in fl.placements if _is_program_room(p)]
        if not rooms:
            continue
        x0 = min(p.rect.x for p in rooms)
        y0 = min(p.rect.y for p in rooms)
        x1 = max(p.rect.x + p.rect.width for p in rooms)
        y1 = max(p.rect.y + p.rect.depth for p in rooms)
        w, d = x1 - x0, y1 - y0
        if w <= 1e-6 or d <= 1e-6:
            continue
        area = w * d
        if best is None or area > best[2]:
            best = (w, d, area)
    if best is None:
        return None
    return best[0], best[1]


def compute_geometry_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, float]:
    occupied = _occupied_footprint(candidate)
    if occupied is None:
        w, d = program.buildable.width, program.buildable.depth
    else:
        w, d = occupied
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
    """
    房间比例质量（Metric Ownership：aspect / slender）。

    不计入 area_accuracy / compactness（分属 program_fit / space_efficiency）。
    """
    penalty = float(metrics.get("aspect_ratio_penalty", 0.0))
    slender = float(metrics.get("slender_room_count", 0.0))
    # 基准 100；细长惩罚 + 房间数轻度扣分
    base = 100.0 - min(45.0, penalty) - slender * 3.0
    return max(0.0, min(100.0, base))

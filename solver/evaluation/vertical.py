"""跨层对齐评价。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, WetStack


def _primary_wet_stack(candidate: LayoutCandidate) -> WetStack | None:
    if candidate.wet_stacks:
        return candidate.wet_stacks[0]
    return None


def _floor_wet_anchor_aligned(candidate: LayoutCandidate) -> float:
    """
    WetStack 跨层对齐分。

    优先用 candidate.wet_stacks（单锚即视为对齐）；
    无 stacks 时回退到各层 deprecated wet_zone_* 镜像比较。
    """
    stack = _primary_wet_stack(candidate)
    if stack is not None:
        # 整栋共享同一 anchor_rect → 天然对齐
        return 1.0

    if len(candidate.floors) < 2:
        return 1.0

    ref = candidate.floors[0]
    if ref.wet_zone_x0 is None or ref.wet_zone_x1 is None:
        return 1.0

    for fl in candidate.floors[1:]:
        if fl.wet_zone_x0 is None or fl.wet_zone_x1 is None:
            continue
        if abs(fl.wet_zone_x0 - ref.wet_zone_x0) > 0.01 or abs(fl.wet_zone_x1 - ref.wet_zone_x1) > 0.01:
            return 0.0
        if ref.wet_zone_y0 is not None and fl.wet_zone_y0 is not None:
            if abs(fl.wet_zone_y0 - ref.wet_zone_y0) > 0.01 or abs(fl.wet_zone_y1 - ref.wet_zone_y1) > 0.01:
                return 0.0
    return 1.0


def compute_vertical_metrics(candidate: LayoutCandidate) -> dict[str, float]:
    stair = 1.0

    if len(candidate.floors) >= 2:
        ref = candidate.floors[0]
        for fl in candidate.floors[1:]:
            if None not in (
                ref.stair_x0,
                ref.stair_x1,
                ref.stair_y0,
                ref.stair_y1,
                fl.stair_x0,
                fl.stair_x1,
                fl.stair_y0,
                fl.stair_y1,
            ):
                if (
                    abs(fl.stair_x0 - ref.stair_x0) > 0.01
                    or abs(fl.stair_x1 - ref.stair_x1) > 0.01
                    or abs(fl.stair_y0 - ref.stair_y0) > 0.01
                    or abs(fl.stair_y1 - ref.stair_y1) > 0.01
                ):
                    stair = 0.0

    wet = _floor_wet_anchor_aligned(candidate)
    return {
        "stair_alignment": stair,
        "wet_stack_alignment": wet,
        "wet_zone_alignment": wet,  # deprecated alias
    }


def vertical_score(metrics: dict[str, float]) -> float:
    stair = metrics.get("stair_alignment", 1.0)
    wet = metrics.get(
        "wet_stack_alignment",
        metrics.get("wet_zone_alignment", 1.0),
    )
    return max(0.0, min(100.0, stair * 50 + wet * 50))

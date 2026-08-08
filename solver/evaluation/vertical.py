"""跨层对齐评价。"""

from __future__ import annotations

from packages.schema.layout import FloorLayout, LayoutCandidate, WetStack


def _is_stair_placement(room_id: str, category: str | None, name: str | None) -> bool:
    return room_id.startswith("stair-") or (
        category == "circulation" and name is not None and "楼梯" in name
    )


def _floor_has_stair_placement(fl: FloorLayout) -> bool:
    return any(
        _is_stair_placement(p.room_id, p.category, p.name) for p in fl.placements
    )


def _stair_box(
    fl: FloorLayout,
) -> tuple[float, float, float, float] | None:
    vals = (fl.stair_x0, fl.stair_y0, fl.stair_x1, fl.stair_y1)
    if None in vals:
        return None
    assert fl.stair_x0 is not None and fl.stair_y0 is not None
    assert fl.stair_x1 is not None and fl.stair_y1 is not None
    return (fl.stair_x0, fl.stair_y0, fl.stair_x1, fl.stair_y1)


def _primary_wet_stack(candidate: LayoutCandidate) -> WetStack | None:
    if candidate.wet_stacks:
        return candidate.wet_stacks[0]
    return None


def _floor_wet_anchor_aligned(candidate: LayoutCandidate) -> float:
    """
    WetStack 跨层对齐分。

    优先用 candidate.wet_stacks（单锚即视为对齐）；
    无 stacks 时回退到各层 deprecated wet_zone_* 镜像比较。
    缺 metadata 时不得默认满分（多层且无可比锚 → 0）。
    """
    stack = _primary_wet_stack(candidate)
    if stack is not None:
        # 整栋共享同一 anchor_rect → 天然对齐
        return 1.0

    if len(candidate.floors) < 2:
        return 1.0

    ref = candidate.floors[0]
    if ref.wet_zone_x0 is None or ref.wet_zone_x1 is None:
        # 无 wet stack、无镜像锚：不可证对齐
        return 0.0

    comparable = 0
    for fl in candidate.floors[1:]:
        if fl.wet_zone_x0 is None or fl.wet_zone_x1 is None:
            continue
        comparable += 1
        if abs(fl.wet_zone_x0 - ref.wet_zone_x0) > 0.01 or abs(
            fl.wet_zone_x1 - ref.wet_zone_x1
        ) > 0.01:
            return 0.0
        if ref.wet_zone_y0 is not None and fl.wet_zone_y0 is not None:
            if abs(fl.wet_zone_y0 - ref.wet_zone_y0) > 0.01 or abs(
                fl.wet_zone_y1 - ref.wet_zone_y1  # type: ignore[operator]
            ) > 0.01:
                return 0.0
    # 仅有一层有锚、其余缺失 → 不可证
    return 1.0 if comparable > 0 else 0.0


def compute_vertical_metrics(candidate: LayoutCandidate) -> dict[str, float]:
    """
    楼梯：评价当前几何 metadata。

    - 单层：1.0（无可跨层比较）
    - 多层且无任何楼梯 placement：1.0（N/A）
    - 有楼梯 placement 但缺 stair_*：0.0（不可证，不得默认成功）
    - 各层均有完整 stair_*：比较对齐
    """
    stair = 1.0

    if len(candidate.floors) >= 2:
        floors_with_stair_pl = [
            fl for fl in candidate.floors if _floor_has_stair_placement(fl)
        ]
        if floors_with_stair_pl:
            boxes: list[tuple[float, float, float, float]] = []
            incomplete = False
            for fl in floors_with_stair_pl:
                box = _stair_box(fl)
                if box is None:
                    incomplete = True
                else:
                    boxes.append(box)
            if incomplete or len(boxes) < 2:
                # 缺 metadata 或不足两层可比较 → 不得默认满分
                stair = 0.0
            else:
                ref = boxes[0]
                for box in boxes[1:]:
                    if any(abs(a - b) > 0.01 for a, b in zip(ref, box, strict=True)):
                        stair = 0.0
                        break

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

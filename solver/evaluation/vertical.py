"""跨层对齐评价。"""

from __future__ import annotations

from packages.schema.layout import FloorLayout, LayoutCandidate
from packages.schema.program import DesignProgram
from solver.geometry.rect import Rect, from_placement, intersection


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


_WET_TAGS = frozenset({"kitchen", "ensuite", "master_bath", "bath", "bathroom"})


def wet_room_ids_for(
    candidate: LayoutCandidate,
    program: DesignProgram | None = None,
) -> set[str]:
    """Wet / kitchen / bath rooms from program + placement category."""
    ids: set[str] = set()
    if program is not None:
        for room in program.rooms:
            cat = room.category.value if hasattr(room.category, "value") else str(room.category or "")
            tags = {str(t).lower() for t in (getattr(room, "tags", None) or [])}
            if cat.lower() == "wet" or tags & _WET_TAGS:
                ids.add(room.id)
    for fl in candidate.floors:
        for p in fl.placements:
            if (p.category or "").lower() == "wet":
                ids.add(p.room_id)
    return ids


def _aabb(rects: list[Rect]) -> Rect:
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.right for r in rects)
    y1 = max(r.bottom for r in rects)
    return Rect(x=x0, y=y0, width=max(0.0, x1 - x0), depth=max(0.0, y1 - y0))


def wet_alignment_from_geometry(
    candidate: LayoutCandidate,
    program: DesignProgram | None = None,
) -> float:
    """IoU of wet-room AABBs across floors. Metadata-only wet_stacks is not a pass."""
    if len(candidate.floors) < 2:
        return 1.0
    wet_ids = wet_room_ids_for(candidate, program)
    occupied: list[list[Rect]] = []
    for fl in candidate.floors:
        rects = [from_placement(p.rect) for p in fl.placements if p.room_id in wet_ids]
        if rects:
            occupied.append(rects)
    if not occupied:
        return 1.0
    if len(occupied) < 2:
        return 0.0
    boxes = [_aabb(group) for group in occupied]
    ref = boxes[0]
    scores: list[float] = []
    for box in boxes[1:]:
        inter = intersection(ref, box)
        if inter is None or inter.area <= 0:
            scores.append(0.0)
            continue
        union = ref.area + box.area - inter.area
        scores.append(inter.area / union if union > 0 else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _floor_wet_anchor_aligned(
    candidate: LayoutCandidate,
    program: DesignProgram | None = None,
) -> float:
    return wet_alignment_from_geometry(candidate, program)


def compute_vertical_metrics(
    candidate: LayoutCandidate,
    program: DesignProgram | None = None,
) -> dict[str, float]:
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

    wet = _floor_wet_anchor_aligned(candidate, program)
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

"""跨层对齐评价。"""

from __future__ import annotations

from collections import defaultdict

from packages.schema.layout import FloorLayout, LayoutCandidate, Violation
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory, RoomSpec, SemanticRole
from packages.schema.vertical_void import (
    DEFAULT_WET_STACK_MIN_IOU,
    VerticalVoidSpec,
    VerticalVoidType,
    floor_ids_in_span,
    min_iou_for_wet_riser_tolerance,
)
from solver.geometry.rect import Rect, from_placement, intersection

_MASTER_BATH_TAGS = frozenset({"master_bath", "master_bathroom", "ensuite"})
_KITCHEN_TAGS = frozenset({"kitchen"})
_BATH_TAGS = frozenset({"bath", "bathroom"})


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


def wet_stack_pairing_key(room: RoomSpec) -> str:
    """跨层湿区配对键：semantic_role 优先，其次 tags，最后泛化 bathroom。"""
    if room.semantic_role is not None:
        return room.semantic_role.value
    tags = {str(t).lower() for t in (room.tags or [])}
    if tags & _KITCHEN_TAGS:
        return SemanticRole.KITCHEN.value
    if tags & _MASTER_BATH_TAGS:
        return SemanticRole.MASTER_BATHROOM.value
    if tags & _BATH_TAGS:
        return SemanticRole.BATHROOM.value
    if room.category == RoomCategory.WET:
        return SemanticRole.BATHROOM.value
    return f"wet:{room.id}"


def rect_iou(a: Rect, b: Rect) -> float:
    inter = intersection(a, b)
    if inter is None or inter.area <= 0:
        return 0.0
    union = a.area + b.area - inter.area
    return inter.area / union if union > 0 else 0.0


def _wet_placements_by_key(
    floor: FloorLayout,
    *,
    wet_ids: set[str],
    room_by_id: dict[str, RoomSpec],
) -> dict[str, list[tuple[str, Rect]]]:
    grouped: dict[str, list[tuple[str, Rect]]] = defaultdict(list)
    for p in floor.placements:
        if p.room_id not in wet_ids:
            continue
        room = room_by_id.get(p.room_id)
        if room is None:
            continue
        key = wet_stack_pairing_key(room)
        grouped[key].append((p.room_id, from_placement(p.rect)))
    return grouped


def _greedy_pair_wet_rooms(
    low: list[tuple[str, Rect]],
    high: list[tuple[str, Rect]],
) -> list[tuple[tuple[str, Rect], tuple[str, Rect]]]:
    if not low or not high:
        return []
    pairs: list[tuple[tuple[str, Rect], tuple[str, Rect]]] = []
    used_high: set[int] = set()
    for low_item in low:
        best_j: int | None = None
        best_iou = -1.0
        for j, high_item in enumerate(high):
            if j in used_high:
                continue
            iou = rect_iou(low_item[1], high_item[1])
            if iou > best_iou:
                best_iou = iou
                best_j = j
        if best_j is None:
            continue
        used_high.add(best_j)
        pairs.append((low_item, high[best_j]))
    return pairs


def _wet_riser_specs_for_adjacent_pair(
    program: DesignProgram,
    low_floor_id: str,
    high_floor_id: str,
) -> list[VerticalVoidSpec]:
    floor_ids = [f.id for f in program.floors]
    matched: list[VerticalVoidSpec] = []
    for spec in program.vertical_voids:
        if spec.void_type != VerticalVoidType.WET_RISER:
            continue
        span_ids = floor_ids_in_span(floor_ids, spec.floor_span)
        if low_floor_id in span_ids and high_floor_id in span_ids:
            matched.append(spec)
    return matched


def min_iou_for_floor_pair(
    program: DesignProgram,
    low_floor_id: str,
    high_floor_id: str,
    *,
    default_min_iou: float = DEFAULT_WET_STACK_MIN_IOU,
) -> float:
    """
    相邻楼层湿区 IoU 下限。

    无覆盖该楼对的 WET_RISER → default_min_iou；有则取各 void 映射后最严（最高）阈值。
    """
    risers = _wet_riser_specs_for_adjacent_pair(program, low_floor_id, high_floor_id)
    if not risers:
        return default_min_iou
    return max(
        min_iou_for_wet_riser_tolerance(spec.alignment_tolerance) for spec in risers
    )


def wet_stack_alignment_violations(
    candidate: LayoutCandidate,
    program: DesignProgram | None,
    *,
    min_iou: float | None = None,
    tolerance: float = 1e-6,
) -> list[Violation]:
    """
    相邻楼层湿区按 pairing key 配对，逐对 IoU 须 ≥ 阈值。

    阈值：显式 ``min_iou`` 覆盖全部楼对；否则按 WET_RISER ``alignment_tolerance`` 映射，
    未覆盖楼对使用 ``DEFAULT_WET_STACK_MIN_IOU``。

    仅在两层均存在同 key 湿区时检查；单层独有的湿区（如仅 F1 厨房）不强制跨层配对。
    """
    if program is None or len(candidate.floors) < 2:
        return []

    wet_ids = wet_room_ids_for(candidate, program)
    if not wet_ids:
        return []

    room_by_id = {r.id: r for r in program.rooms}
    violations: list[Violation] = []

    for i in range(len(candidate.floors) - 1):
        low_floor = candidate.floors[i]
        high_floor = candidate.floors[i + 1]
        pair_min_iou = (
            min_iou
            if min_iou is not None
            else min_iou_for_floor_pair(
                program, low_floor.floor_id, high_floor.floor_id
            )
        )
        risers = _wet_riser_specs_for_adjacent_pair(
            program, low_floor.floor_id, high_floor.floor_id
        )
        low_by_key = _wet_placements_by_key(
            low_floor, wet_ids=wet_ids, room_by_id=room_by_id
        )
        high_by_key = _wet_placements_by_key(
            high_floor, wet_ids=wet_ids, room_by_id=room_by_id
        )
        shared_keys = set(low_by_key) & set(high_by_key)
        for key in sorted(shared_keys):
            pairs = _greedy_pair_wet_rooms(low_by_key[key], high_by_key[key])
            for (rid_a, rect_a), (rid_b, rect_b) in pairs:
                iou = rect_iou(rect_a, rect_b)
                if iou + tolerance >= pair_min_iou:
                    continue
                tol_hint = ""
                if risers:
                    tol_hint = (
                        f"；WET_RISER tolerance="
                        f"{risers[0].alignment_tolerance:.2f}m"
                    )
                violations.append(
                    Violation(
                        constraint_id="vertical.wet_stack_alignment",
                        room_ids=sorted({rid_a, rid_b}),
                        message=(
                            f"湿区跨层对齐不足：{rid_a}↔{rid_b}（{key}）"
                            f"IoU={iou:.3f} < {pair_min_iou:.3f}"
                            f"（{low_floor.floor_id}↔{high_floor.floor_id}{tol_hint}）"
                        ),
                        measured_value=iou,
                        required_value=pair_min_iou,
                        hard=True,
                        source="system",
                    )
                )
    return violations


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

"""ADR-010 Step B — 湿区跨层锚点放置（生成器侧）。"""

from __future__ import annotations

from packages.schema.layout import FloorLayout, PlacementRect
from packages.schema.program import DesignProgram
from packages.schema.room import RoomSpec

from solver.evaluation.vertical import rect_iou, wet_stack_pairing_key
from solver.geometry.free_rects import subtract_rects
from solver.geometry.rect import Rect, from_placement, intersection, intersects
from solver.topology.zoning import wet_stack_group_for_room


def wet_target_area_by_floor(program: DesignProgram) -> dict[str, float]:
    """各层湿区（WetStack 成员）目标面积合计。"""
    totals: dict[str, float] = {f.id: 0.0 for f in program.floors}
    for room in program.rooms:
        if wet_stack_group_for_room(room) is None:
            continue
        fid = room.floor_id or program.floors[0].id
        totals[fid] = totals.get(fid, 0.0) + room.target_area
    return totals


def anchor_floor_id(program: DesignProgram) -> str:
    """湿区面积需求最大的楼层作为锚层（先行布局并导出跨层锚）。"""
    totals = wet_target_area_by_floor(program)
    if not totals:
        return program.floors[0].id
    return max(totals, key=lambda fid: totals[fid])


def collect_wet_anchor_rects(
    floor_layout: FloorLayout,
    program: DesignProgram,
) -> dict[str, Rect]:
    """从锚层实际放置收集 pairing key → 锚矩形。"""
    room_by_id = {r.id: r for r in program.rooms}
    anchors: dict[str, Rect] = {}
    for placement in floor_layout.placements:
        room = room_by_id.get(placement.room_id)
        if room is None or wet_stack_group_for_room(room) is None:
            continue
        key = wet_stack_pairing_key(room)
        anchors[key] = from_placement(placement.rect)
    return anchors


def _largest_anchor_overlap(free_rects: list[Rect], anchor: Rect) -> Rect | None:
    best: Rect | None = None
    for free in free_rects:
        inter = intersection(free, anchor)
        if inter is None:
            continue
        if best is None or inter.area > best.area:
            best = inter
    return best


def _placement_in_region(
    region: Rect,
    *,
    min_area: float,
    max_area: float,
) -> PlacementRect | None:
    if region.area + 1e-9 < min_area:
        return None
    w = region.width
    h = region.depth
    if w <= 0 or h <= 0:
        return None
    area = min(region.area, max_area)
    if region.area <= max_area + 1e-9:
        return PlacementRect(x=region.x, y=region.y, width=w, depth=h)
    if w > 0 and area / w <= h:
        return PlacementRect(x=region.x, y=region.y, width=w, depth=area / w)
    if h > 0:
        width = min(w, area / h)
        if width > 0:
            return PlacementRect(x=region.x, y=region.y, width=width, depth=h)
    return PlacementRect(x=region.x, y=region.y, width=w, depth=h)


def _anchor_aligned_candidates(
    pack: Rect,
    anchor: Rect,
    *,
    min_area: float,
    max_area: float,
) -> list[PlacementRect]:
    """在 pack 内生成与 anchor 重叠的候选放置。"""
    out: list[PlacementRect] = []
    inter = intersection(pack, anchor)
    if inter is not None:
        placed = _placement_in_region(inter, min_area=min_area, max_area=max_area)
        if placed is not None:
            out.append(placed)

    # 尝试与 anchor 同 footprint（跨层对齐首选）
    exact = Rect(x=anchor.x, y=anchor.y, width=anchor.width, depth=anchor.depth)
    if intersects(pack, exact):
        clipped = intersection(pack, exact)
        if clipped is not None:
            placed = _placement_in_region(clipped, min_area=min_area, max_area=max_area)
            if placed is not None:
                out.append(placed)

    w = pack.width
    h = pack.depth
    if w <= 0 or h <= 0:
        return out
    area = min(w * h, max_area)
    if w > 0 and area / w <= h:
        depth = area / w
        for y in (pack.y, pack.bottom - depth):
            if y < pack.y - 1e-9 or y + depth > pack.bottom + 1e-9:
                continue
            cand = PlacementRect(x=pack.x, y=y, width=w, depth=depth)
            if from_placement(cand).area + 1e-9 >= min_area:
                out.append(cand)
    if h > 0:
        width = min(w, area / h)
        for x in (pack.x, pack.right - width):
            if x < pack.x - 1e-9 or x + width > pack.right + 1e-9:
                continue
            cand = PlacementRect(x=x, y=pack.y, width=width, depth=h)
            if from_placement(cand).area + 1e-9 >= min_area:
                out.append(cand)
    return out


def place_room_at_wet_anchor(
    pack: Rect,
    anchor: Rect,
    *,
    min_area: float,
    max_area: float,
) -> PlacementRect | None:
    """在 pack 区内优先与 anchor 高 IoU 对齐的放置。"""
    best: PlacementRect | None = None
    best_iou = -1.0
    seen: set[tuple[float, float, float, float]] = set()
    for cand in _anchor_aligned_candidates(
        pack, anchor, min_area=min_area, max_area=max_area
    ):
        key = (cand.x, cand.y, cand.width, cand.depth)
        if key in seen:
            continue
        seen.add(key)
        rect = from_placement(cand)
        if rect.area + 1e-9 < min_area:
            continue
        iou = rect_iou(rect, anchor)
        if iou > best_iou:
            best_iou = iou
            best = cand
    if best is not None and best_iou > 1e-9:
        return best
    return None


def preplace_wet_anchored_rooms(
    rooms: list[RoomSpec],
    *,
    footprint: Rect,
    occupied: list[Rect],
    wet_anchors: dict[str, Rect],
) -> dict[str, PlacementRect]:
    """
    在 zone 打包前预放置带锚点的湿区房间。

    按目标面积降序，避免小卫生间占掉厨房锚带。
    """
    placements: dict[str, PlacementRect] = {}
    free = subtract_rects([footprint], occupied)
    if not free:
        return placements

    candidates = []
    for room in rooms:
        if wet_stack_group_for_room(room) is None:
            continue
        key = wet_stack_pairing_key(room)
        if key in wet_anchors:
            candidates.append(room)
    candidates.sort(key=lambda r: r.target_area, reverse=True)

    for room in candidates:
        key = wet_stack_pairing_key(room)
        anchor = wet_anchors.get(key)
        if anchor is None:
            continue
        region = _largest_anchor_overlap(free, anchor)
        if region is None:
            continue
        placed = place_room_at_wet_anchor(
            region,
            anchor,
            min_area=room.resolved_min_area(),
            max_area=room.resolved_max_area(),
        )
        if placed is None:
            continue
        placements[room.id] = placed
        free = subtract_rects(free, [from_placement(placed)])
    return placements


def _shrink_larger_toward_smaller(
    larger: Rect,
    smaller: Rect,
    *,
    min_area: float,
    min_iou: float,
) -> Rect | None:
    """把偏大湿区裁向偏小侧，使 IoU≥阈值且不低于 min_area。"""
    if larger.area + 1e-9 < min_area:
        return None
    # 优先：完全落到 smaller footprint（IoU=1）
    if smaller.area + 1e-9 >= min_area:
        exact = Rect(
            x=smaller.x, y=smaller.y, width=smaller.width, depth=smaller.depth
        )
        if rect_iou(exact, smaller) + 1e-9 >= min_iou:
            return exact
    # 同宽条带：只削深度（smaller 嵌在 larger 投影内时 IoU≈smaller.depth/depth）
    if abs(larger.x - smaller.x) <= 1e-6 and abs(larger.width - smaller.width) <= 1e-6:
        w = larger.width
        if w <= 1e-9:
            return None
        max_depth = smaller.depth / max(min_iou, 1e-6)
        min_depth = min_area / w
        if min_depth > max_depth + 1e-9:
            return None
        depth = min(larger.depth, max(min_depth, smaller.depth))
        if depth > max_depth + 1e-9:
            depth = max_depth
        y = smaller.y
        if y < larger.y - 1e-9 or y + depth > larger.bottom + 1e-9:
            y = larger.y
        cand = Rect(x=larger.x, y=y, width=w, depth=depth)
        if cand.area + 1e-9 >= min_area and rect_iou(cand, smaller) + 1e-9 >= min_iou:
            return cand
    # 同高条带：只削宽度
    if abs(larger.y - smaller.y) <= 1e-6 and abs(larger.depth - smaller.depth) <= 1e-6:
        h = larger.depth
        if h <= 1e-9:
            return None
        max_width = smaller.width / max(min_iou, 1e-6)
        min_width = min_area / h
        if min_width > max_width + 1e-9:
            return None
        width = min(larger.width, max(min_width, smaller.width))
        if width > max_width + 1e-9:
            width = max_width
        x = smaller.x
        if x < larger.x - 1e-9 or x + width > larger.right + 1e-9:
            x = larger.x
        cand = Rect(x=x, y=larger.y, width=width, depth=h)
        if cand.area + 1e-9 >= min_area and rect_iou(cand, smaller) + 1e-9 >= min_iou:
            return cand
    return None


def nudge_wet_stack_alignment(
    candidate,
    program: DesignProgram,
    *,
    min_iou: float | None = None,
) -> list:
    """
    跨层同 key 湿区 IoU 不足时，裁切偏大一侧（余量留给后续走廊填缝）。

    返回可能已修改的 FloorLayout 列表（与 candidate.floors 同序）。
    """
    from packages.schema.layout import FloorLayout, RoomPlacement
    from packages.schema.vertical_void import DEFAULT_WET_STACK_MIN_IOU
    from solver.evaluation.vertical import (
        _greedy_pair_wet_rooms,
        _wet_placements_by_key,
        min_iou_for_floor_pair,
        wet_room_ids_for,
    )

    if len(candidate.floors) < 2:
        return list(candidate.floors)

    thr = min_iou if min_iou is not None else DEFAULT_WET_STACK_MIN_IOU
    wet_ids = wet_room_ids_for(candidate, program)
    room_by_id = {r.id: r for r in program.rooms}
    floors: list[FloorLayout] = [fl.model_copy(deep=True) for fl in candidate.floors]
    by_floor_placements: dict[str, dict[str, RoomPlacement]] = {
        fl.floor_id: {p.room_id: p for p in fl.placements} for fl in floors
    }

    for i in range(len(floors) - 1):
        low = floors[i]
        high = floors[i + 1]
        pair_min = (
            thr
            if min_iou is not None
            else min_iou_for_floor_pair(program, low.floor_id, high.floor_id)
        )
        low_by = _wet_placements_by_key(
            low, wet_ids=wet_ids, room_by_id=room_by_id
        )
        high_by = _wet_placements_by_key(
            high, wet_ids=wet_ids, room_by_id=room_by_id
        )
        for key in sorted(set(low_by) & set(high_by)):
            for (rid_a, rect_a), (rid_b, rect_b) in _greedy_pair_wet_rooms(
                low_by[key], high_by[key]
            ):
                if rect_iou(rect_a, rect_b) + 1e-6 >= pair_min:
                    continue
                # 裁较大者
                if rect_a.area >= rect_b.area:
                    shrink_id, shrink_rect, keep_rect = rid_a, rect_a, rect_b
                    shrink_floor = low.floor_id
                else:
                    shrink_id, shrink_rect, keep_rect = rid_b, rect_b, rect_a
                    shrink_floor = high.floor_id
                room = room_by_id.get(shrink_id)
                if room is None:
                    continue
                new_rect = _shrink_larger_toward_smaller(
                    shrink_rect,
                    keep_rect,
                    min_area=room.resolved_min_area(),
                    min_iou=pair_min,
                )
                if new_rect is None:
                    continue
                p = by_floor_placements[shrink_floor].get(shrink_id)
                if p is None:
                    continue
                by_floor_placements[shrink_floor][shrink_id] = p.model_copy(
                    update={
                        "rect": PlacementRect(
                            x=new_rect.x,
                            y=new_rect.y,
                            width=new_rect.width,
                            depth=new_rect.depth,
                        )
                    }
                )

    out: list[FloorLayout] = []
    for fl in floors:
        placed = list(by_floor_placements[fl.floor_id].values())
        # 保持原顺序
        order = {p.room_id: i for i, p in enumerate(fl.placements)}
        placed.sort(key=lambda p: order.get(p.room_id, 10_000))
        out.append(fl.model_copy(update={"placements": placed}))
    return out

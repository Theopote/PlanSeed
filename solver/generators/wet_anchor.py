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

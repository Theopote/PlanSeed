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


def _wet_stack_swap_donor_ok(room: RoomSpec | None, *, room_id: str) -> bool:
    """可与错位湿区对调的占用者：卧室/辅助/走廊；不碰门厅楼梯厨客餐厅。"""
    from packages.schema.room import RoomCategory
    from solver.semantics.roles import (
        TAG_BEDROOM,
        TAG_MASTER_BEDROOM,
        has_any_tag,
        is_dining,
        is_foyer,
        is_kitchen,
        is_laundry,
        is_living,
        is_storage,
        is_study,
    )

    if room_id.startswith(("stair-", "void-", "foyer-")):
        return False
    if room_id.startswith("circ-"):
        return True
    if room is None:
        return False
    if is_foyer(room) or is_living(room) or is_kitchen(room) or is_dining(room):
        return False
    if wet_stack_group_for_room(room) is not None:
        return False
    if is_storage(room) or is_laundry(room) or is_study(room):
        return True
    if has_any_tag(room, TAG_BEDROOM) or has_any_tag(room, TAG_MASTER_BEDROOM):
        return True
    return room.category == RoomCategory.PRIVATE


def realign_wet_stack_by_occupant_swap(
    candidate,
    program: DesignProgram,
    *,
    min_iou: float | None = None,
) -> list:
    """
    finalize 后湿区 IoU=0 时：把错位层湿区与压住锚足迹的卧室/走廊对调。

    锚层几何已定（含 clip/grow）；仅挪另一层，避免再改坏 F1。
    """
    from packages.schema.layout import FloorLayout, RoomPlacement
    from packages.schema.vertical_void import DEFAULT_WET_STACK_MIN_IOU
    from solver.evaluation.vertical import (
        _greedy_pair_wet_rooms,
        _wet_placements_by_key,
        min_iou_for_floor_pair,
        wet_room_ids_for,
    )
    from solver.evaluation.weights import DEFAULT_WEIGHTS

    if len(candidate.floors) < 2:
        return list(candidate.floors)

    thr = min_iou if min_iou is not None else DEFAULT_WET_STACK_MIN_IOU
    wet_ids = wet_room_ids_for(candidate, program)
    room_by_id = {r.id: r for r in program.rooms}
    anchor_fid = anchor_floor_id(program)
    floors: list[FloorLayout] = [fl.model_copy(deep=True) for fl in candidate.floors]
    by_floor: dict[str, dict[str, RoomPlacement]] = {
        fl.floor_id: {p.room_id: p for p in fl.placements} for fl in floors
    }
    aspect_thr = DEFAULT_WEIGHTS.aspect_ratio_threshold + 1e-6

    def _aspect_ok(rect: Rect) -> bool:
        short = min(rect.width, rect.depth)
        long = max(rect.width, rect.depth)
        return long / max(short, 0.01) <= aspect_thr

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
                # 锚层足迹为 keep；另一层湿区去对调占用者
                if low.floor_id == anchor_fid:
                    keep_fid, keep_rect = low.floor_id, rect_a
                    move_fid, move_rid, move_rect = high.floor_id, rid_b, rect_b
                elif high.floor_id == anchor_fid:
                    keep_fid, keep_rect = high.floor_id, rect_b
                    move_fid, move_rid, move_rect = low.floor_id, rid_a, rect_a
                else:
                    keep_fid, keep_rect = low.floor_id, rect_a
                    move_fid, move_rid, move_rect = high.floor_id, rid_b, rect_b
                _ = keep_fid  # 锚层只读
                move_room = room_by_id.get(move_rid)
                if move_room is None:
                    continue
                if (
                    keep_rect.area + 1e-9 < move_room.resolved_min_area()
                    or keep_rect.area > move_room.resolved_max_area() + 1e-9
                ):
                    continue
                if not _aspect_ok(keep_rect):
                    continue
                # 错位层上盖住锚足迹的主占用者
                placed_map = by_floor[move_fid]
                best_oid: str | None = None
                best_cover = 0.0
                for oid, op in placed_map.items():
                    if oid == move_rid:
                        continue
                    inter = intersection(from_placement(op.rect), keep_rect)
                    if inter is None:
                        continue
                    if inter.area > best_cover:
                        best_cover = inter.area
                        best_oid = oid
                if best_oid is None or best_cover < keep_rect.area * 0.5:
                    continue
                donor_p = placed_map[best_oid]
                donor_rect = from_placement(donor_p.rect)
                # 占用者应大致落在锚足迹上（允许 finalize 后同脚印）
                if rect_iou(donor_rect, keep_rect) + 1e-6 < 0.5 and best_cover < keep_rect.area * 0.85:
                    continue
                donor_room = room_by_id.get(best_oid)
                if not _wet_stack_swap_donor_ok(donor_room, room_id=best_oid):
                    continue
                # 占用者换到湿区旧位：面积可暂低于 min（后续 grow）
                if donor_room is not None:
                    if move_rect.area > donor_room.resolved_max_area() + 1e-9:
                        continue
                elif not best_oid.startswith("circ-"):
                    continue
                wet_p = placed_map.get(move_rid)
                if wet_p is None:
                    continue
                # 对调：湿区落到锚足迹；若与 live circ 不通则内缩通行条
                plan = _wet_swap_with_access_band(
                    keep_rect=keep_rect,
                    donor_id=best_oid,
                    donor_rect=move_rect,
                    placed_map=placed_map,
                    move_rid=move_rid,
                    move_room=move_room,
                    donor_room=donor_room,
                    room_by_id=room_by_id,
                    pair_min=pair_min,
                    aspect_ok=_aspect_ok,
                )
                if plan is None:
                    continue
                wet_rect, extra_circs, donor_after, neighbor_shrinks = plan
                placed_map[move_rid] = wet_p.model_copy(
                    update={
                        "rect": PlacementRect(
                            x=wet_rect.x,
                            y=wet_rect.y,
                            width=wet_rect.width,
                            depth=wet_rect.depth,
                        )
                    }
                )
                placed_map[best_oid] = donor_p.model_copy(
                    update={
                        "rect": PlacementRect(
                            x=donor_after.x,
                            y=donor_after.y,
                            width=donor_after.width,
                            depth=donor_after.depth,
                        )
                    }
                )
                for nid, nrect in neighbor_shrinks:
                    np = placed_map.get(nid)
                    if np is None:
                        continue
                    placed_map[nid] = np.model_copy(
                        update={
                            "rect": PlacementRect(
                                x=nrect.x,
                                y=nrect.y,
                                width=nrect.width,
                                depth=nrect.depth,
                            )
                        }
                    )
                from packages.schema.layout import PlacementSource

                for ci, crect in enumerate(extra_circs):
                    cid = f"circ-{move_fid}-wet{ci}"
                    n = ci
                    while cid in placed_map:
                        n += 1
                        cid = f"circ-{move_fid}-wet{n}"
                    placed_map[cid] = RoomPlacement(
                        room_id=cid,
                        floor_id=move_fid,
                        rect=PlacementRect(
                            x=crect.x,
                            y=crect.y,
                            width=crect.width,
                            depth=crect.depth,
                        ),
                        source=PlacementSource.GENERATED,
                        name="circulation",
                        category="circulation",
                    )

    out: list[FloorLayout] = []
    for fl in floors:
        placed = list(by_floor[fl.floor_id].values())
        order = {p.room_id: i for i, p in enumerate(fl.placements)}
        placed.sort(key=lambda p: order.get(p.room_id, 10_000))
        out.append(fl.model_copy(update={"placements": placed}))
    return out


def _circulation_component_ids(placed_map: dict, *, exclude: str | None = None) -> set[str]:
    """从楼梯出发、仅经 circ/foyer/stair 连通的通行组件。"""
    from solver.geometry.rect import shared_edge_length

    nodes = {
        rid: from_placement(p.rect)
        for rid, p in placed_map.items()
        if rid != exclude
        and rid.startswith(("circ-", "stair-", "foyer-"))
    }
    roots = [rid for rid in nodes if rid.startswith("stair-")]
    if not roots:
        return set()
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        cr = nodes[cur]
        for oid, orect in nodes.items():
            if oid in seen:
                continue
            if shared_edge_length(cr, orect) + 1e-9 >= 0.5:
                stack.append(oid)
    return seen


def _wet_swap_with_access_band(
    *,
    keep_rect: Rect,
    donor_id: str,
    donor_rect: Rect,
    placed_map: dict,
    move_rid: str,
    move_room: RoomSpec,
    donor_room: RoomSpec | None,
    room_by_id: dict[str, RoomSpec],
    pair_min: float,
    aspect_ok,
) -> tuple[Rect, list[Rect], Rect, list[tuple[str, Rect]]] | None:
    """
    湿区落到 keep_rect；若与 live circ 不通，内缩通行条并向邻房延伸。

    返回 (wet_rect, extra_circs, donor_rect, neighbor_shrinks)；
    donor 落在湿区旧位 donor_rect（通常为 move 前湿区矩形）。
    """
    from solver.geometry.rect import shared_edge_length

    _ = donor_room
    live_circ = _circulation_component_ids(placed_map, exclude=move_rid)

    def _touches_live_circ(rect: Rect) -> bool:
        for oid in live_circ:
            op = placed_map.get(oid)
            if op is None:
                continue
            if shared_edge_length(rect, from_placement(op.rect)) + 1e-9 >= 0.5:
                return True
        return False

    if _touches_live_circ(keep_rect):
        return keep_rect, [], donor_rect, []

    band = 0.9
    min_area = move_room.resolved_min_area()
    max_area = move_room.resolved_max_area()

    # 优先南缘内缩（B09：锚在北翼、走廊在南）
    for side in ("south", "north", "east", "west"):
        if side == "south":
            if keep_rect.depth <= band + 0.3:
                continue
            wet = Rect(
                x=keep_rect.x,
                y=keep_rect.y,
                width=keep_rect.width,
                depth=keep_rect.depth - band,
            )
            strip = Rect(
                x=keep_rect.x,
                y=keep_rect.bottom - band,
                width=keep_rect.width,
                depth=band,
            )
        elif side == "north":
            if keep_rect.depth <= band + 0.3:
                continue
            wet = Rect(
                x=keep_rect.x,
                y=keep_rect.y + band,
                width=keep_rect.width,
                depth=keep_rect.depth - band,
            )
            strip = Rect(
                x=keep_rect.x, y=keep_rect.y, width=keep_rect.width, depth=band
            )
        elif side == "east":
            if keep_rect.width <= band + 0.3:
                continue
            wet = Rect(
                x=keep_rect.x,
                y=keep_rect.y,
                width=keep_rect.width - band,
                depth=keep_rect.depth,
            )
            strip = Rect(
                x=keep_rect.right - band,
                y=keep_rect.y,
                width=band,
                depth=keep_rect.depth,
            )
        else:
            if keep_rect.width <= band + 0.3:
                continue
            wet = Rect(
                x=keep_rect.x + band,
                y=keep_rect.y,
                width=keep_rect.width - band,
                depth=keep_rect.depth,
            )
            strip = Rect(
                x=keep_rect.x, y=keep_rect.y, width=band, depth=keep_rect.depth
            )
        if wet.area + 1e-9 < min_area or wet.area > max_area + 1e-9:
            continue
        if not aspect_ok(wet):
            continue
        if rect_iou(wet, keep_rect) + 1e-6 < pair_min:
            continue
        if _touches_live_circ(strip):
            return wet, [strip], donor_rect, []
        extended = _extend_access_strip_through_neighbors(
            strip,
            placed_map,
            move_rid=move_rid,
            donor_id=donor_id,
            live_circ=live_circ,
            room_by_id=room_by_id,
        )
        if extended is None:
            continue
        full_strip, shrinks = extended
        return wet, [full_strip], donor_rect, shrinks

    # 无法开通行：整块对调
    return keep_rect, [], donor_rect, []


def _extend_access_strip_through_neighbors(
    strip: Rect,
    placed_map: dict,
    *,
    move_rid: str,
    donor_id: str,
    live_circ: set[str],
    room_by_id: dict[str, RoomSpec],
) -> tuple[Rect, list[tuple[str, Rect]]] | None:
    """把通行条沿长边伸进邻房，直到碰到 live circ。"""
    from solver.geometry.rect import shared_edge_length

    # 水平条（南北缘）：向西/东延伸
    horizontal = strip.width >= strip.depth
    live_rects = [
        from_placement(placed_map[oid].rect)
        for oid in live_circ
        if oid in placed_map
    ]
    if not live_rects:
        return None

    def _try_extend(direction: str) -> tuple[Rect, list[tuple[str, Rect]]] | None:
        shrinks: list[tuple[str, Rect]] = []
        cur = strip
        for _ in range(4):
            if any(
                shared_edge_length(cur, lr) + 1e-9 >= 0.5 for lr in live_rects
            ):
                return cur, shrinks
            # 找贴边邻房
            best_id: str | None = None
            best_rect: Rect | None = None
            for oid, op in placed_map.items():
                if oid in (move_rid, donor_id) or oid.startswith(
                    ("stair-", "void-")
                ):
                    continue
                if oid.startswith(("circ-", "foyer-")):
                    continue
                orect = from_placement(op.rect)
                if horizontal and direction == "west":
                    if abs(orect.right - cur.left) > 1e-6:
                        continue
                    y0 = max(orect.top, cur.top)
                    y1 = min(orect.bottom, cur.bottom)
                    if y1 - y0 < 0.5:
                        continue
                elif horizontal and direction == "east":
                    if abs(orect.left - cur.right) > 1e-6:
                        continue
                    y0 = max(orect.top, cur.top)
                    y1 = min(orect.bottom, cur.bottom)
                    if y1 - y0 < 0.5:
                        continue
                elif (not horizontal) and direction == "north":
                    if abs(orect.bottom - cur.top) > 1e-6:
                        continue
                    x0 = max(orect.left, cur.left)
                    x1 = min(orect.right, cur.right)
                    if x1 - x0 < 0.5:
                        continue
                elif (not horizontal) and direction == "south":
                    if abs(orect.top - cur.bottom) > 1e-6:
                        continue
                    x0 = max(orect.left, cur.left)
                    x1 = min(orect.right, cur.right)
                    if x1 - x0 < 0.5:
                        continue
                else:
                    continue
                best_id, best_rect = oid, orect
                break
            if best_id is None or best_rect is None:
                return None
            room = room_by_id.get(best_id)
            band = strip.depth if horizontal else strip.width
            if horizontal and direction == "west":
                # 从邻房东侧切 band 高的条并入
                take_w = best_rect.width
                # 只切与 strip 同 y 带
                new_piece = Rect(
                    x=best_rect.x,
                    y=cur.y,
                    width=take_w,
                    depth=cur.depth,
                )
                # 邻房上推/下推：保留 strip 带以外部分 → 整房从南缘削（若 strip 贴底）
                if abs(best_rect.bottom - cur.bottom) <= 1e-6:
                    shrunk = Rect(
                        x=best_rect.x,
                        y=best_rect.y,
                        width=best_rect.width,
                        depth=best_rect.depth - cur.depth,
                    )
                elif abs(best_rect.top - cur.top) <= 1e-6:
                    shrunk = Rect(
                        x=best_rect.x,
                        y=best_rect.y + cur.depth,
                        width=best_rect.width,
                        depth=best_rect.depth - cur.depth,
                    )
                else:
                    return None
                merged = Rect(
                    x=new_piece.x,
                    y=cur.y,
                    width=cur.right - new_piece.x,
                    depth=cur.depth,
                )
            elif horizontal and direction == "east":
                if abs(best_rect.bottom - cur.bottom) <= 1e-6:
                    shrunk = Rect(
                        x=best_rect.x,
                        y=best_rect.y,
                        width=best_rect.width,
                        depth=best_rect.depth - cur.depth,
                    )
                elif abs(best_rect.top - cur.top) <= 1e-6:
                    shrunk = Rect(
                        x=best_rect.x,
                        y=best_rect.y + cur.depth,
                        width=best_rect.width,
                        depth=best_rect.depth - cur.depth,
                    )
                else:
                    return None
                merged = Rect(
                    x=cur.x,
                    y=cur.y,
                    width=best_rect.right - cur.x,
                    depth=cur.depth,
                )
            else:
                return None
            if shrunk.width <= 1e-6 or shrunk.depth <= 1e-6:
                return None
            if room is not None and shrunk.area + 1e-9 < room.resolved_min_area():
                return None
            shrinks.append((best_id, shrunk))
            cur = merged
            _ = band
        if any(shared_edge_length(cur, lr) + 1e-9 >= 0.5 for lr in live_rects):
            return cur, shrinks
        return None

    if horizontal:
        for d in ("west", "east"):
            got = _try_extend(d)
            if got is not None:
                return got
    else:
        for d in ("north", "south"):
            got = _try_extend(d)
            if got is not None:
                return got
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

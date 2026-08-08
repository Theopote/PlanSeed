"""
跨区局部重切 — topology → geometry（Phase 2.1.2）。

当局部缝隙修补失败时：在同层小 AABB 内重切若干房间，
强制 required 对先共边占位，其余房间在剩余矩形内 Guillotine 打包。

仍禁止：整层重跑、跨层重切、为门移动楼梯核。
"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, PlacementRect, RoomPlacement
from packages.schema.program import DesignProgram
from solver.geometry.rect import Rect, contains, from_placement, intersects
from solver.geometry.snap import snap_value
from solver.topology.access import MIN_ACCESS_WALL
from solver.topology.doors import shared_boundary_between

# 保守上限：避免退化成「几乎整层重优化」
MAX_RESLICE_ROOMS = 6
MAX_PAIR_CENTER_DIST = 8.0
MAX_REGION_FLOOR_FRACTION = 0.55
MIN_SPAN_MODULES = 2


def _is_stair(p: RoomPlacement) -> bool:
    return p.room_id.startswith("stair-") or (
        (p.category or "") == "circulation" and "楼梯" in (p.name or "")
    )


def _aabb(rects: list[Rect]) -> Rect:
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.right for r in rects)
    y1 = max(r.bottom for r in rects)
    return Rect(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)


def _center(r: Rect) -> tuple[float, float]:
    return r.x + r.width / 2, r.y + r.depth / 2


def _center_dist(a: Rect, b: Rect) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _set_rect(p: RoomPlacement, r: Rect) -> None:
    p.rect = PlacementRect(x=r.x, y=r.y, width=r.width, depth=r.depth)


def _weight_of(p: RoomPlacement, program: DesignProgram) -> float:
    for room in program.rooms:
        if room.id == p.room_id:
            return max(room.target_area, 1.0)
    return max(p.rect.area, 1.0)


def _floor_placements(
    candidate: LayoutCandidate, floor_id: str
) -> list[RoomPlacement]:
    for fl in candidate.floors:
        if fl.floor_id == floor_id:
            return list(fl.placements)
    return []


def collect_reslice_members(
    pa: RoomPlacement,
    pb: RoomPlacement,
    floor_placements: list[RoomPlacement],
    *,
    max_rooms: int = MAX_RESLICE_ROOMS,
) -> list[RoomPlacement] | None:
    """
    取必连对 AABB 内相交的非楼梯房间；超限时按与中点距离截断。
    """
    ra, rb = from_placement(pa.rect), from_placement(pb.rect)
    if _center_dist(ra, rb) > MAX_PAIR_CENTER_DIST + 1e-9:
        return None

    seed_aabb = _aabb([ra, rb])
    candidates = [
        p
        for p in floor_placements
        if not _is_stair(p)
        and intersects(from_placement(p.rect), seed_aabb)
    ]
    # 确保包含对端
    by_id = {p.room_id: p for p in candidates}
    by_id[pa.room_id] = pa
    by_id[pb.room_id] = pb
    members = list(by_id.values())

    if len(members) > max_rooms:
        mx = (ra.x + ra.width / 2 + rb.x + rb.width / 2) / 2
        my = (ra.y + ra.depth / 2 + rb.y + rb.depth / 2) / 2

        def key(p: RoomPlacement) -> tuple[float, str]:
            if p.room_id in (pa.room_id, pb.room_id):
                return (-1.0, p.room_id)
            c = _center(from_placement(p.rect))
            return (((c[0] - mx) ** 2 + (c[1] - my) ** 2) ** 0.5, p.room_id)

        members = sorted(members, key=key)[:max_rooms]
        # 截断后必须仍含对端
        ids = {p.room_id for p in members}
        if pa.room_id not in ids or pb.room_id not in ids:
            return None

    region = _aabb([from_placement(p.rect) for p in members])
    for p in floor_placements:
        if _is_stair(p) and intersects(from_placement(p.rect), region):
            # 楼梯核落入重切区 → 放弃（避免动核）
            return None
    return members


def _split_rect(
    region: Rect,
    frac: float,
    *,
    module: float,
    horizontal: bool,
) -> tuple[Rect, Rect] | None:
    min_span = module * MIN_SPAN_MODULES
    frac = min(0.85, max(0.15, frac))
    if horizontal:
        cut = snap_value(region.x + region.width * frac, module)
        cut = max(region.x + min_span, min(region.right - min_span, cut))
        left = Rect(x=region.x, y=region.y, width=cut - region.x, depth=region.depth)
        right = Rect(
            x=cut, y=region.y, width=region.right - cut, depth=region.depth
        )
        if left.width < min_span or right.width < min_span:
            return None
        return left, right
    cut = snap_value(region.y + region.depth * frac, module)
    cut = max(region.y + min_span, min(region.bottom - min_span, cut))
    top = Rect(x=region.x, y=region.y, width=region.width, depth=cut - region.y)
    bottom = Rect(
        x=region.x, y=cut, width=region.width, depth=region.bottom - cut
    )
    if top.depth < min_span or bottom.depth < min_span:
        return None
    return top, bottom


def place_pair_sharing_edge(
    pa: RoomPlacement,
    pb: RoomPlacement,
    region: Rect,
    *,
    module: float,
    weight_a: float,
    weight_b: float,
    min_wall: float = MIN_ACCESS_WALL,
) -> bool:
    """在 region 内二分放置 pa/pb，保证共边 ≥ min_wall。"""
    min_span = module * MIN_SPAN_MODULES
    total = weight_a + weight_b or 1.0
    frac = weight_a / total
    horizontal = region.width >= region.depth
    split = _split_rect(region, frac, module=module, horizontal=horizontal)
    if split is None:
        return False
    r1, r2 = split
    # 共边长度 = 分割轴的垂直方向跨度
    shared = region.depth if horizontal else region.width
    if shared + 1e-9 < min_wall:
        return False
    if r1.width < min_span or r1.depth < min_span:
        return False
    if r2.width < min_span or r2.depth < min_span:
        return False
    _set_rect(pa, r1)
    _set_rect(pb, r2)
    return shared_boundary_between(pa, pb, min_length=min_wall) is not None


def _pack_rooms_in_rect(
    rooms: list[RoomPlacement],
    region: Rect,
    *,
    program: DesignProgram,
    module: float,
) -> bool:
    """简易 Guillotine：按权重对半切；失败返回 False 并保持调用方回滚。"""
    if not rooms:
        return True
    if len(rooms) == 1:
        _set_rect(rooms[0], region)
        return True

    weights = [_weight_of(r, program) for r in rooms]
    total = sum(weights) or 1.0
    half = total / 2
    cum = 0.0
    split_idx = 1
    for i, w in enumerate(weights[:-1]):
        cum += w
        if cum >= half:
            split_idx = i + 1
            break
    g1, g2 = rooms[:split_idx], rooms[split_idx:]
    w1 = sum(weights[:split_idx]) or 1.0
    frac = w1 / total
    horizontal = region.width >= region.depth
    split = _split_rect(region, frac, module=module, horizontal=horizontal)
    if split is None:
        return False
    a, b = split
    return _pack_rooms_in_rect(
        g1, a, program=program, module=module
    ) and _pack_rooms_in_rect(g2, b, program=program, module=module)


def try_reslice_required_pair(
    program: DesignProgram,
    candidate: LayoutCandidate,
    pa: RoomPlacement,
    pb: RoomPlacement,
    *,
    module: float,
    min_wall: float = MIN_ACCESS_WALL,
    floor_bounds: Rect | None = None,
) -> bool:
    """
    在局部 AABB 内重切，使 pa—pb 必连共边。

    成功则已写入 placements；失败则恢复原矩形。
    """
    if pa.floor_id != pb.floor_id:
        return False
    if _is_stair(pa) or _is_stair(pb):
        return False
    if shared_boundary_between(pa, pb, min_length=min_wall) is not None:
        return False

    floor_id = pa.floor_id
    placements = _floor_placements(candidate, floor_id)
    members = collect_reslice_members(pa, pb, placements)
    if not members:
        return False

    region = _aabb([from_placement(p.rect) for p in members])
    bounds = floor_bounds or Rect(
        x=0.0,
        y=0.0,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )
    if not contains(bounds, region):
        # 裁到楼层内
        x0 = max(bounds.left, region.x)
        y0 = max(bounds.top, region.y)
        x1 = min(bounds.right, region.right)
        y1 = min(bounds.bottom, region.bottom)
        if x1 - x0 < module * MIN_SPAN_MODULES * 2:
            return False
        if y1 - y0 < module * MIN_SPAN_MODULES * 2:
            return False
        region = Rect(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)

    floor_area = max(bounds.area, 1.0)
    if region.area / floor_area > MAX_REGION_FLOOR_FRACTION + 1e-9:
        return False

    # 区域不得与非成员非楼梯重叠（否则重切会踩到外人）
    member_ids = {p.room_id for p in members}
    for p in placements:
        if p.room_id in member_ids or _is_stair(p):
            continue
        if intersects(from_placement(p.rect), region):
            return False

    backup = {p.room_id: p.rect.model_copy() for p in members}

    rest = [p for p in members if p.room_id not in (pa.room_id, pb.room_id)]
    # 稳定序
    rest.sort(key=lambda p: p.room_id)
    wa, wb = _weight_of(pa, program), _weight_of(pb, program)
    pair_w = wa + wb
    rest_w = sum(_weight_of(p, program) for p in rest) or 0.0

    ok = False
    if not rest:
        ok = place_pair_sharing_edge(
            pa, pb, region, module=module, weight_a=wa, weight_b=wb, min_wall=min_wall
        )
    else:
        total = pair_w + rest_w
        frac = pair_w / total
        horizontal = region.width >= region.depth
        split = _split_rect(region, frac, module=module, horizontal=horizontal)
        if split is not None:
            pair_region, rest_region = split
            for pr, rr in ((pair_region, rest_region), (rest_region, pair_region)):
                if place_pair_sharing_edge(
                    pa,
                    pb,
                    pr,
                    module=module,
                    weight_a=wa,
                    weight_b=wb,
                    min_wall=min_wall,
                ) and _pack_rooms_in_rect(
                    rest, rr, program=program, module=module
                ):
                    ok = True
                    break

    if not ok:
        for p in members:
            p.rect = backup[p.room_id]
        return False

    # 最终校验：对端共边 + 成员互不重叠 + 均在 region/bounds 内
    if shared_boundary_between(pa, pb, min_length=min_wall) is None:
        for p in members:
            p.rect = backup[p.room_id]
        return False

    rects = [(p, from_placement(p.rect)) for p in members]
    for i, (pi, ri) in enumerate(rects):
        if not contains(bounds, ri):
            for p in members:
                p.rect = backup[p.room_id]
            return False
        for pj, rj in rects[i + 1 :]:
            if intersects(ri, rj):
                for p in members:
                    p.rect = backup[p.room_id]
                return False
    return True

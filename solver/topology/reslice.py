"""
跨区局部重切 — topology → geometry（Phase 2.1.2 / 2.1.3）。

当局部缝隙修补失败时：在同层小 AABB 内重切若干房间，
强制 required 对先共边占位，其余房间在剩余矩形内 Guillotine 打包。

Phase 2.1.3：楼梯核视为**固定障碍**（不移动）；
从区域挖洞得多块 free rect；必要时扩绕行带再打包。

仍禁止：整层重跑、跨层重切、移动楼梯核。
"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, PlacementRect, RoomPlacement
from packages.schema.program import DesignProgram
from solver.geometry.free_rects import subtract_rects
from solver.geometry.rect import Rect, contains, from_placement, intersects, shared_edge_length
from solver.geometry.snap import snap_value
from solver.topology.access import MIN_ACCESS_WALL
from solver.topology.doors import shared_boundary_between

# 保守上限：避免退化成「几乎整层重优化」
MAX_RESLICE_ROOMS = 6
MAX_PAIR_CENTER_DIST = 8.0
MAX_REGION_FLOOR_FRACTION = 0.55
MIN_SPAN_MODULES = 2
BYPASS_SPAN_MODULES = 4  # 绕核扩边带约 1.2m（module=0.3）


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


def _clip_to_bounds(region: Rect, bounds: Rect) -> Rect | None:
    x0 = max(bounds.left, region.x)
    y0 = max(bounds.top, region.y)
    x1 = min(bounds.right, region.right)
    y1 = min(bounds.bottom, region.bottom)
    if x1 - x0 < 1e-9 or y1 - y0 < 1e-9:
        return None
    return Rect(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)


def _outsider_intersects(
    region: Rect,
    placements: list[RoomPlacement],
    member_ids: set[str],
) -> bool:
    for p in placements:
        if p.room_id in member_ids or _is_stair(p):
            continue
        if intersects(from_placement(p.rect), region):
            return True
    return False


def collect_reslice_members(
    pa: RoomPlacement,
    pb: RoomPlacement,
    floor_placements: list[RoomPlacement],
    *,
    max_rooms: int = MAX_RESLICE_ROOMS,
) -> list[RoomPlacement] | None:
    """
    取必连对 AABB 内相交的非楼梯房间；超限时按与中点距离截断。

    楼梯核不再导致放弃：由调用方作为 obstacle 挖洞。
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
        ids = {p.room_id for p in members}
        if pa.room_id not in ids or pb.room_id not in ids:
            return None

    return members


def collect_stair_obstacles(
    region: Rect,
    floor_placements: list[RoomPlacement],
) -> list[Rect]:
    """与 region 相交的楼梯核矩形（固定障碍）。"""
    out: list[Rect] = []
    for p in floor_placements:
        if not _is_stair(p):
            continue
        r = from_placement(p.rect)
        if intersects(r, region):
            out.append(r)
    return out


def expand_region_for_bypass(
    region: Rect,
    obstacles: list[Rect],
    *,
    bounds: Rect,
    placements: list[RoomPlacement],
    member_ids: set[str],
    module: float,
    floor_area: float,
) -> tuple[Rect, list[Rect]]:
    """
    若障碍把区域剖成互不共边碎片，尝试向四周扩绕行带。

    返回 (最终 region, free_rects)；失败则返回原 region 与其挖洞结果。
    """
    bypass = module * BYPASS_SPAN_MODULES
    min_span = module * MIN_SPAN_MODULES

    def free_of(reg: Rect) -> list[Rect]:
        parts = subtract_rects([reg], obstacles)
        return [p for p in parts if p.width + 1e-9 >= min_span and p.depth + 1e-9 >= min_span]

    def connected(parts: list[Rect]) -> bool:
        if len(parts) <= 1:
            return True
        n = len(parts)
        adj = [set() for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if shared_edge_length(parts[i], parts[j]) > 1e-6:
                    adj[i].add(j)
                    adj[j].add(i)
        seen = {0}
        stack = [0]
        while stack:
            cur = stack.pop()
            for nb in adj[cur]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        return len(seen) == n

    base_free = free_of(region)
    if not obstacles or (base_free and connected(base_free)):
        # 无障碍，或已连通：仍可能需扩边以增大最大块
        if base_free and (
            not obstacles
            or max(p.area for p in base_free) >= 0.35 * region.area
        ):
            return region, base_free

    # 增长方向：(dx0, dy0, dx1, dy1) 加在 left/top/right/bottom
    deltas = [
        (0.0, 0.0, 0.0, bypass),  # south
        (0.0, -bypass, 0.0, 0.0),  # north
        (0.0, 0.0, bypass, 0.0),  # east
        (-bypass, 0.0, 0.0, 0.0),  # west
        (0.0, -bypass, 0.0, bypass),  # NS
        (-bypass, 0.0, bypass, 0.0),  # EW
        (0.0, -bypass / 2, 0.0, bypass),
        (0.0, -bypass, 0.0, bypass / 2),
    ]

    best: tuple[float, Rect, list[Rect]] | None = None
    for dx0, dy0, dx1, dy1 in deltas:
        cand = Rect(
            x=region.x + dx0,
            y=region.y + dy0,
            width=region.width - dx0 + dx1,
            depth=region.depth - dy0 + dy1,
        )
        clipped = _clip_to_bounds(cand, bounds)
        if clipped is None:
            continue
        if clipped.area / floor_area > MAX_REGION_FLOOR_FRACTION + 1e-9:
            continue
        if _outsider_intersects(clipped, placements, member_ids):
            continue
        free = free_of(clipped)
        if not free:
            continue
        max_a = max(p.area for p in free)
        score = max_a + (1000.0 if connected(free) else 0.0)
        if best is None or score > best[0]:
            best = (score, clipped, free)

    if best is None:
        return region, base_free
    return best[1], best[2]


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


def _pack_rooms_in_free_rects(
    rooms: list[RoomPlacement],
    free_rects: list[Rect],
    *,
    program: DesignProgram,
    module: float,
) -> bool:
    """将房间分配到多块 free rect 并分别 Guillotine。"""
    if not rooms:
        return True
    if not free_rects:
        return False

    free_rects = sorted(free_rects, key=lambda r: r.area, reverse=True)
    rooms = sorted(rooms, key=lambda p: p.room_id)
    total_w = sum(_weight_of(r, program) for r in rooms) or 1.0
    total_a = sum(r.area for r in free_rects) or 1.0

    primary = free_rects[0]
    others = free_rects[1:]
    share = primary.area / total_a
    target_w = max(total_w * share, 1e-9)

    cum = 0.0
    k = 0
    for i, r in enumerate(rooms):
        cum += _weight_of(r, program)
        k = i + 1
        if cum >= target_w and (others or k == len(rooms)):
            break
    if k == 0:
        k = 1
    if not others:
        k = len(rooms)

    g1, g2 = rooms[:k], rooms[k:]
    if not _pack_rooms_in_rect(g1, primary, program=program, module=module):
        return False
    return _pack_rooms_in_free_rects(g2, others, program=program, module=module)


def _try_pack_pair_and_rest(
    pa: RoomPlacement,
    pb: RoomPlacement,
    rest: list[RoomPlacement],
    free_rects: list[Rect],
    *,
    program: DesignProgram,
    module: float,
    min_wall: float,
) -> bool:
    """在 free_rects 上：对端共边占位 + 其余多矩形打包。"""
    if not free_rects:
        return False
    involved = [pa, pb, *rest]
    snap = {p.room_id: p.rect.model_copy() for p in involved}

    def restore() -> None:
        for p in involved:
            p.rect = snap[p.room_id].model_copy()

    wa, wb = _weight_of(pa, program), _weight_of(pb, program)
    pair_w = wa + wb
    rest_w = sum(_weight_of(p, program) for p in rest) or 0.0
    ordered = sorted(free_rects, key=lambda r: r.area, reverse=True)

    # 策略 A：单块足够大 → 经典对半（pair | rest）
    for fi, fr in enumerate(ordered):
        if not rest:
            restore()
            if place_pair_sharing_edge(
                pa, pb, fr, module=module, weight_a=wa, weight_b=wb, min_wall=min_wall
            ):
                return True
            continue
        total = pair_w + rest_w
        frac = pair_w / total
        horizontal = fr.width >= fr.depth
        split = _split_rect(fr, frac, module=module, horizontal=horizontal)
        if split is None:
            continue
        rem = [r for i, r in enumerate(ordered) if i != fi]
        for pr, rr in (split, (split[1], split[0])):
            restore()
            if place_pair_sharing_edge(
                pa, pb, pr, module=module, weight_a=wa, weight_b=wb, min_wall=min_wall
            ) and _pack_rooms_in_free_rects(
                rest, [rr, *rem], program=program, module=module
            ):
                return True

    # 策略 B：仅在最大块放 pair，其余块装 rest
    if rest and len(ordered) >= 2:
        restore()
        primary, rem = ordered[0], ordered[1:]
        if place_pair_sharing_edge(
            pa,
            pb,
            primary,
            module=module,
            weight_a=wa,
            weight_b=wb,
            min_wall=min_wall,
        ) and _pack_rooms_in_free_rects(
            rest, rem, program=program, module=module
        ):
            return True

    restore()
    return False


def try_reslice_required_pair(
    program: DesignProgram,
    candidate: LayoutCandidate,
    pa: RoomPlacement,
    pb: RoomPlacement,
    *,
    module: float,
    min_wall: float = MIN_ACCESS_WALL,
    floor_bounds: Rect | None = None,
    protected_room_ids: set[str] | None = None,
) -> bool:
    """
    在局部 AABB（可绕核扩边）内重切，使 pa—pb 必连共边。

    成功则已写入 placements；失败则恢复原矩形。楼梯核不动。
    含 LayoutLocks protected 成员时直接放弃（禁止偷偷解锁）。
    """
    if pa.floor_id != pb.floor_id:
        return False
    if _is_stair(pa) or _is_stair(pb):
        return False
    protected = protected_room_ids or set()
    if pa.room_id in protected or pb.room_id in protected:
        return False
    if shared_boundary_between(pa, pb, min_length=min_wall) is not None:
        return False

    floor_id = pa.floor_id
    placements = _floor_placements(candidate, floor_id)
    members = collect_reslice_members(pa, pb, placements)
    if not members:
        return False
    if any(p.room_id in protected for p in members):
        return False

    member_ids = {p.room_id for p in members}
    region = _aabb([from_placement(p.rect) for p in members])
    bounds = floor_bounds or Rect(
        x=0.0,
        y=0.0,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )
    clipped = _clip_to_bounds(region, bounds)
    if clipped is None:
        return False
    region = clipped

    floor_area = max(bounds.area, 1.0)
    if region.area / floor_area > MAX_REGION_FLOOR_FRACTION + 1e-9:
        return False

    # 非成员非楼梯踩区 → 放弃（避免踩外人）；楼梯单独挖洞
    if _outsider_intersects(region, placements, member_ids):
        return False

    obstacles = collect_stair_obstacles(region, placements)
    region, free_rects = expand_region_for_bypass(
        region,
        obstacles,
        bounds=bounds,
        placements=placements,
        member_ids=member_ids,
        module=module,
        floor_area=floor_area,
    )
    # 扩边后可能撞上新楼梯段
    obstacles = collect_stair_obstacles(region, placements)
    min_span = module * MIN_SPAN_MODULES
    free_rects = [
        r
        for r in subtract_rects([region], obstacles)
        if r.width + 1e-9 >= min_span and r.depth + 1e-9 >= min_span
    ]
    if not free_rects:
        return False
    if region.area / floor_area > MAX_REGION_FLOOR_FRACTION + 1e-9:
        return False
    if _outsider_intersects(region, placements, member_ids):
        return False

    backup = {p.room_id: p.rect.model_copy() for p in members}
    rest = [p for p in members if p.room_id not in (pa.room_id, pb.room_id)]
    rest.sort(key=lambda p: p.room_id)

    ok = _try_pack_pair_and_rest(
        pa,
        pb,
        rest,
        free_rects,
        program=program,
        module=module,
        min_wall=min_wall,
    )

    if not ok:
        for p in members:
            p.rect = backup[p.room_id]
        return False

    # 最终校验：对端共边 + 成员互不重叠 + 不撞障碍 + 在 bounds 内
    if shared_boundary_between(pa, pb, min_length=min_wall) is None:
        for p in members:
            p.rect = backup[p.room_id]
        return False

    rects = [(p, from_placement(p.rect)) for p in members]
    for i, (_pi, ri) in enumerate(rects):
        if not contains(bounds, ri):
            for p in members:
                p.rect = backup[p.room_id]
            return False
        for obs in obstacles:
            if intersects(ri, obs):
                for p in members:
                    p.rect = backup[p.room_id]
                return False
        for _pj, rj in rects[i + 1 :]:
            if intersects(ri, rj):
                for p in members:
                    p.rect = backup[p.room_id]
                return False
    return True

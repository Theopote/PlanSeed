"""
Phase 2A/2.2 — 门洞标注与 polish。

原则：
- **禁止**为放门回改 / 重优化 RoomPlacement
- 2A：required SpaceConnection 须有足够共边 → DoorOpening
- 2.2：门宽 / 净宽 / 侧铰 / 开启方向；SVG 画门扇
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from packages.schema.layout import DoorOpening, LayoutCandidate, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.topology import SpaceConnection, SpaceConnectionType
from solver.geometry.rect import from_placement, shared_edge_length
from solver.topology.constants import MIN_ACCESS_WALL

# 需要同层共边才能落开口的连接类型（楼梯 / 入口另议）
_OPENING_TYPES = frozenset(
    {
        SpaceConnectionType.OPEN,
        SpaceConnectionType.DOOR,
        SpaceConnectionType.PASSAGE,
    }
)

DEFAULT_DOOR_WIDTH = 0.9
PHYSICAL_MIN_WIDTH = 0.7  # 物理可用下限（内部默认，非法规）
PREFERRED_CLEAR_WIDTH = 0.8  # 偏好净宽
MIN_CLEAR_WIDTH = PREFERRED_CLEAR_WIDTH  # 兼容旧名
MIN_WALL_REVEAL = 0.05


def _is_private_category(category: str | None) -> bool:
    return (category or "").lower() == "private"


def _is_wet_category(category: str | None) -> bool:
    return (category or "").lower() == "wet"


def _wet_private_neighbor_map(
    openings: list[DoorOpening],
    by_id: dict[str, RoomPlacement],
) -> dict[str, set[str]]:
    """统计 wet 房间已直接连通的 private 邻居（用于 spanning tree 扇出控制）。"""
    from collections import defaultdict

    wet_private: dict[str, set[str]] = defaultdict(set)
    for op in openings:
        pa = by_id.get(op.room_a_id)
        pb = by_id.get(op.room_b_id)
        if pa is None or pb is None:
            continue
        if _is_wet_category(pa.category) and _is_private_category(pb.category):
            wet_private[pa.room_id].add(pb.room_id)
        elif _is_wet_category(pb.category) and _is_private_category(pa.category):
            wet_private[pb.room_id].add(pa.room_id)
    return wet_private


def _would_exceed_wet_private_fanout(
    pa: RoomPlacement,
    pb: RoomPlacement,
    wet_private: dict[str, set[str]],
) -> bool:
    if _is_wet_category(pa.category) and _is_private_category(pb.category):
        existing = wet_private.get(pa.room_id, set())
        return len(existing) >= 1 and pb.room_id not in existing
    if _is_wet_category(pb.category) and _is_private_category(pa.category):
        existing = wet_private.get(pb.room_id, set())
        return len(existing) >= 1 and pa.room_id not in existing
    return False


def _reachable_from_nodes(
    starts: set[str],
    target: str,
    adj: dict[str, list[str]],
    node_set: set[str],
    *,
    excluded_edge: tuple[str, str] | None = None,
) -> bool:
    """从已访问节点集合能否不经过 excluded_edge 到达 target（仅走 adj）。"""
    from collections import deque

    if target in starts:
        return True
    seen = set(starts)
    q: deque[str] = deque(starts)
    while q:
        cur = q.popleft()
        for nb in adj.get(cur, []):
            if nb not in node_set or nb in seen:
                continue
            if excluded_edge is not None and _pair_key(cur, nb) == excluded_edge:
                continue
            if nb == target:
                return True
            seen.add(nb)
            q.append(nb)
    return False


def _is_wet_private_pair(pa: RoomPlacement, pb: RoomPlacement) -> bool:
    return (_is_wet_category(pa.category) and _is_private_category(pb.category)) or (
        _is_wet_category(pb.category) and _is_private_category(pa.category)
    )


def _spanning_wet_edge_allowed(
    pa: RoomPlacement,
    pb: RoomPlacement,
    key: tuple[str, str],
    wet_work: dict[str, set[str]],
    *,
    forced_wet_keys: set[tuple[str, str]],
    blocked_wet_keys: set[tuple[str, str]],
) -> bool:
    if not _is_wet_private_pair(pa, pb):
        return True
    if key in forced_wet_keys:
        return True
    if key in blocked_wet_keys:
        return False
    return not _would_exceed_wet_private_fanout(pa, pb, wet_work)


def _spanning_visit_set(
    adj: dict[str, list[str]],
    by_id: dict[str, RoomPlacement],
    anchors: list[str],
    ids: list[str],
    wet_private: dict[str, set[str]],
    *,
    excluded_edges: set[tuple[str, str]],
    seen_pairs: set[tuple[str, str]],
    forced_wet_keys: set[tuple[str, str]] | None = None,
    blocked_wet_keys: set[tuple[str, str]] | None = None,
) -> set[str]:
    """spanning BFS 可达房间（含 seen_pairs 与可新增的 OPEN 边）。"""
    from collections import deque

    forced_wet = forced_wet_keys or set()
    blocked_wet = blocked_wet_keys or set()
    node_set = set(ids)
    visited: set[str] = set()
    wet_work = {k: set(v) for k, v in wet_private.items()}

    for start in anchors:
        if start in visited or start not in by_id:
            continue
        q: deque[str] = deque([start])
        visited.add(start)
        while q:
            cur = q.popleft()
            for nb in sorted(adj.get(cur, [])):
                if nb in visited or nb not in node_set:
                    continue
                key = _pair_key(cur, nb)
                if key in excluded_edges:
                    continue
                if key in seen_pairs:
                    visited.add(nb)
                    q.append(nb)
                    continue
                pa, pb = by_id[cur], by_id[nb]
                if not _spanning_wet_edge_allowed(
                    pa,
                    pb,
                    key,
                    wet_work,
                    forced_wet_keys=forced_wet,
                    blocked_wet_keys=blocked_wet,
                ):
                    continue
                visited.add(nb)
                q.append(nb)
                _record_wet_private_pair(pa, pb, wet_work)
    return visited


def _planned_access_covers_floor(
    ctx: _FloorGraphContext,
    prior_openings: list[DoorOpening],
    seen_pairs: set[tuple[str, str]],
    *,
    omit_pp_keys: set[tuple[str, str]] | None = None,
    blocked_wet_keys: set[tuple[str, str]] | None = None,
    forced_wet_keys: set[tuple[str, str]] | None = None,
) -> bool:
    """intent + spanning OPEN 能否覆盖本层全部房间（联合隐私规则）。"""
    omit_pp = omit_pp_keys or set()
    blocked_wet = blocked_wet_keys or set()
    forced_wet = forced_wet_keys or set()
    kept_openings = [
        op
        for op in prior_openings
        if _pair_key(op.room_a_id, op.room_b_id) not in omit_pp
    ]
    kept_seen = {k for k in seen_pairs if k not in omit_pp}
    wet_private = _wet_private_neighbor_map(kept_openings, ctx.by_id)
    tree_keys, _ = _plan_private_private_span_edges(
        ctx.adj,
        ctx.by_id,
        ctx.anchors,
        ctx.ids,
        wet_private,
        seen_pairs=kept_seen,
        omit_pp_keys=omit_pp,
        blocked_wet_keys=blocked_wet,
        forced_wet_keys=forced_wet,
    )
    visited = _spanning_visit_set(
        ctx.adj,
        ctx.by_id,
        ctx.anchors,
        ctx.ids,
        wet_private,
        excluded_edges=omit_pp,
        seen_pairs=kept_seen | set(tree_keys),
        forced_wet_keys=forced_wet,
        blocked_wet_keys=blocked_wet,
    )
    return visited == set(ctx.ids)


def _record_wet_private_pair(
    pa: RoomPlacement,
    pb: RoomPlacement,
    wet_private: dict[str, set[str]],
) -> None:
    if _is_wet_category(pa.category) and _is_private_category(pb.category):
        wet_private.setdefault(pa.room_id, set()).add(pb.room_id)
    elif _is_wet_category(pb.category) and _is_private_category(pa.category):
        wet_private.setdefault(pb.room_id, set()).add(pa.room_id)


def _private_private_pair(pa: RoomPlacement, pb: RoomPlacement) -> bool:
    return _is_private_category(pa.category) and _is_private_category(pb.category)


@dataclass(frozen=True)
class _JointPrivacyPlan:
    """规则1/2 联合删边计划：omit=不落门/spanning 排除；forced=被迫保留并打标。"""

    omit_pp_keys: set[tuple[str, str]]
    forced_pp_keys: set[tuple[str, str]]
    blocked_wet_keys: set[tuple[str, str]]
    forced_wet_keys: set[tuple[str, str]]


def _collect_rule1_pp_candidates(
    openings: list[DoorOpening],
    ctx: _FloorGraphContext,
    required_pp: set[tuple[str, str]],
) -> set[tuple[str, str]]:
    """规则1：可移除的非 required 私密-私密 intent 门。"""
    candidates: set[tuple[str, str]] = set()
    for op in openings:
        key = _pair_key(op.room_a_id, op.room_b_id)
        if key in required_pp:
            continue
        pa = ctx.by_id.get(op.room_a_id)
        pb = ctx.by_id.get(op.room_b_id)
        if pa is None or pb is None or not _private_private_pair(pa, pb):
            continue
        candidates.add(key)
    return candidates


def _collect_rule2_wet_fanout_candidates(
    ctx: _FloorGraphContext,
    wet_private: dict[str, set[str]],
) -> set[tuple[str, str]]:
    """规则2：湿区已有一间 private 后，其余 wet-private 共墙边为候选排除。"""
    candidates: set[tuple[str, str]] = set()
    for key in ctx.edge_bound:
        pa = ctx.by_id[key[0]]
        pb = ctx.by_id[key[1]]
        if not _is_wet_private_pair(pa, pb):
            continue
        if _would_exceed_wet_private_fanout(pa, pb, wet_private):
            candidates.add(key)
    return candidates


def _plan_joint_privacy_edges(
    ctx: _FloorGraphContext,
    openings: list[DoorOpening],
    intents: list[SpaceConnection],
    seen_pairs: set[tuple[str, str]],
) -> _JointPrivacyPlan:
    """
    规则1/2 联合校验：先合并候选删边，再一次性做连通分析；
    不可达时按规则2优先、规则1次之恢复被迫边。
    """
    required_pp: set[tuple[str, str]] = set()
    for conn in intents:
        if conn.required:
            required_pp.add(_pair_key(conn.a, conn.b))

    rule1 = _collect_rule1_pp_candidates(openings, ctx, required_pp)
    wet_private = _wet_private_neighbor_map(openings, ctx.by_id)
    rule2 = _collect_rule2_wet_fanout_candidates(ctx, wet_private)
    removal = rule1 | rule2

    if _planned_access_covers_floor(
        ctx,
        openings,
        seen_pairs,
        omit_pp_keys=removal & rule1,
        blocked_wet_keys=removal & rule2,
    ):
        return _JointPrivacyPlan(
            omit_pp_keys=removal & rule1,
            forced_pp_keys=set(),
            blocked_wet_keys=removal & rule2,
            forced_wet_keys=set(),
        )

    forced_pp: set[tuple[str, str]] = set()
    forced_wet: set[tuple[str, str]] = set()
    remaining = set(removal)

    while remaining and not _planned_access_covers_floor(
        ctx,
        openings,
        seen_pairs,
        omit_pp_keys=(remaining & rule1) - forced_pp,
        blocked_wet_keys=(remaining & rule2) - forced_wet,
        forced_wet_keys=forced_wet,
    ):
        restored: tuple[str, str] | None = None
        for key in sorted(remaining):
            if key not in rule2:
                continue
            trial_remaining = remaining - {key}
            if _planned_access_covers_floor(
                ctx,
                openings,
                seen_pairs,
                omit_pp_keys=(trial_remaining & rule1) - forced_pp,
                blocked_wet_keys=(trial_remaining & rule2) - forced_wet,
                forced_wet_keys=forced_wet | {key},
            ):
                restored = key
                forced_wet.add(key)
                remaining = trial_remaining
                break
        if restored is not None:
            continue

        for key in sorted(remaining):
            if key not in rule1:
                continue
            trial_remaining = remaining - {key}
            if _planned_access_covers_floor(
                ctx,
                openings,
                seen_pairs,
                omit_pp_keys=(trial_remaining & rule1) - forced_pp,
                blocked_wet_keys=(trial_remaining & rule2) - forced_wet,
                forced_wet_keys=forced_wet,
            ):
                restored = key
                forced_pp.add(key)
                remaining = trial_remaining
                break
        if restored is not None:
            continue

        # 单条恢复不足：贪心先恢复规则2，再规则1
        key = min(remaining, key=lambda k: (0 if k in rule2 else 1, k))
        if key in rule2:
            forced_wet.add(key)
        else:
            forced_pp.add(key)
        remaining.remove(key)

    return _JointPrivacyPlan(
        omit_pp_keys=(remaining & rule1) - forced_pp,
        forced_pp_keys=forced_pp,
        blocked_wet_keys=(remaining & rule2) - forced_wet,
        forced_wet_keys=forced_wet,
    )


@dataclass(frozen=True)
class SharedBoundary:
    floor_id: str
    length: float
    axis: str  # "x" | "y"
    mid_x: float
    mid_y: float
    # 共边线段端点（沿墙）
    x0: float
    y0: float
    x1: float
    y1: float


def find_placements(
    candidate: LayoutCandidate, room_id: str
) -> list[RoomPlacement]:
    return [
        p
        for fl in candidate.floors
        for p in fl.placements
        if p.room_id == room_id
    ]


def shared_boundary_between(
    a: RoomPlacement,
    b: RoomPlacement,
    *,
    min_length: float = MIN_ACCESS_WALL,
) -> SharedBoundary | None:
    """两放置同层且共边 ≥ min_length 时返回边界几何；否则 None。"""
    if a.floor_id != b.floor_id:
        return None
    ra, rb = from_placement(a.rect), from_placement(b.rect)
    length = shared_edge_length(ra, rb)
    if length + 1e-9 < min_length:
        return None

    tol = 1e-6
    # 竖向共享边（左右）→ 墙沿 y，axis=y
    for ax, bx in ((ra.left, rb.right), (ra.right, rb.left)):
        if abs(ax - bx) <= tol:
            y0 = max(ra.top, rb.top)
            y1 = min(ra.bottom, rb.bottom)
            if y1 - y0 > tol:
                return SharedBoundary(
                    floor_id=a.floor_id,
                    length=y1 - y0,
                    axis="y",
                    mid_x=ax,
                    mid_y=(y0 + y1) / 2,
                    x0=ax,
                    y0=y0,
                    x1=ax,
                    y1=y1,
                )
    # 水平共享边（上下）→ 墙沿 x，axis=x
    for ay, by in ((ra.top, rb.bottom), (ra.bottom, rb.top)):
        if abs(ay - by) <= tol:
            x0 = max(ra.left, rb.left)
            x1 = min(ra.right, rb.right)
            if x1 - x0 > tol:
                return SharedBoundary(
                    floor_id=a.floor_id,
                    length=x1 - x0,
                    axis="x",
                    mid_x=(x0 + x1) / 2,
                    mid_y=ay,
                    x0=x0,
                    y0=ay,
                    x1=x1,
                    y1=ay,
                )
    return None


def opening_connections(program: DesignProgram) -> list[SpaceConnection]:
    """全部开口类 AccessIntent（required + preferred）。"""
    if program.access_graph is None:
        return []
    return [
        c
        for c in program.access_graph.connections
        if c.type in _OPENING_TYPES
        and not str(c.a).startswith("exterior")
        and not str(c.b).startswith("exterior")
    ]


def required_opening_connections(program: DesignProgram) -> list[SpaceConnection]:
    return [c for c in opening_connections(program) if c.required]


def preferred_opening_connections(program: DesignProgram) -> list[SpaceConnection]:
    return [c for c in opening_connections(program) if not c.required]


def missing_shared_boundaries(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    min_length: float = MIN_ACCESS_WALL,
    only_required: bool = True,
) -> list[tuple[SpaceConnection, float]]:
    """
    返回缺少足够共边的开口连接。
    only_required=True → hard 必连；False → 含 soft 偏好。
    """
    missing: list[tuple[SpaceConnection, float]] = []
    conns = (
        required_opening_connections(program)
        if only_required
        else opening_connections(program)
    )
    for conn in conns:
        pas = find_placements(candidate, conn.a)
        pbs = find_placements(candidate, conn.b)
        if not pas or not pbs:
            missing.append((conn, 0.0))
            continue
        best = 0.0
        ok = False
        for pa in pas:
            for pb in pbs:
                if pa.floor_id != pb.floor_id:
                    continue
                length = shared_edge_length(
                    from_placement(pa.rect), from_placement(pb.rect)
                )
                best = max(best, length)
                if shared_boundary_between(pa, pb, min_length=min_length) is not None:
                    ok = True
        if not ok:
            missing.append((conn, best))
    return missing


def _rank_swing_pref(p: RoomPlacement) -> tuple[int, float, str]:
    """开启方向偏好：卧室/私密 > 湿区 > 公共 > 交通；同级偏大房间。"""
    cat = (p.category or "other").lower()
    cat_rank = {
        "private": 0,
        "wet": 1,
        "public": 2,
        "service": 3,
        "circulation": 4,
        "other": 3,
    }.get(cat, 3)
    return (cat_rank, -p.rect.area, p.room_id)


def choose_swing_room(
    pa: RoomPlacement, pb: RoomPlacement
) -> RoomPlacement:
    """门扇优先开入私密/使用房间，避免堵走廊。"""
    return min((pa, pb), key=_rank_swing_pref)


def _hinge_geometry(
    boundary: SharedBoundary,
    swing: RoomPlacement,
    *,
    door_width: float,
) -> tuple[float, float, float, float, Literal["left", "right"]]:
    """
    返回 (cx, cy, hinge_x, hinge_y, hinge_side)。

    洞口在共边内居中（留 reveal）；铰链取沿墙「远离 swing 房间中心」的一端，
    便于门扇开入房间时少挡主要空间。
    """
    w = min(door_width, max(MIN_CLEAR_WIDTH, boundary.length - 2 * MIN_WALL_REVEAL))
    w = min(w, boundary.length)
    half = w / 2

    if boundary.axis == "y":
        # 竖墙：沿 y
        y_lo = boundary.y0
        y_hi = boundary.y1
        mid = boundary.mid_y
        c0 = max(y_lo + MIN_WALL_REVEAL, mid - half)
        c1 = c0 + w
        if c1 > y_hi - MIN_WALL_REVEAL + 1e-9:
            c1 = y_hi - MIN_WALL_REVEAL
            c0 = c1 - w
        c0 = max(y_lo, c0)
        c1 = min(y_hi, c0 + w)
        cy = (c0 + c1) / 2
        cx = boundary.mid_x
        # 铰链：取离 swing 中心更远的端
        sy = swing.rect.y + swing.rect.depth / 2
        if abs(c0 - sy) >= abs(c1 - sy):
            hx, hy = cx, c0
            hinge_at_low = True
        else:
            hx, hy = cx, c1
            hinge_at_low = False
        # swing 在墙东侧 → 面西看门：low(y小/北) = 右侧？ 
        # 模型 y 增大向南。面西时：上北(y小)=右？ 面西：左=南(y大)，右=北(y小)
        # 简化约定：hinge_side 以「swing 内面门、墙在身前」：
        swing_east = (swing.rect.x + swing.rect.width / 2) > cx
        if swing_east:
            # 面西：left=南(high y), right=北(low y)
            hinge_side: Literal["left", "right"] = (
                "right" if hinge_at_low else "left"
            )
        else:
            # 面东：left=北(low), right=南(high)
            hinge_side = "left" if hinge_at_low else "right"
        return cx, cy, hx, hy, hinge_side

    # 水平墙：沿 x
    x_lo, x_hi = boundary.x0, boundary.x1
    mid = boundary.mid_x
    c0 = max(x_lo + MIN_WALL_REVEAL, mid - half)
    c1 = c0 + w
    if c1 > x_hi - MIN_WALL_REVEAL + 1e-9:
        c1 = x_hi - MIN_WALL_REVEAL
        c0 = c1 - w
    c0 = max(x_lo, c0)
    c1 = min(x_hi, c0 + w)
    cx = (c0 + c1) / 2
    cy = boundary.mid_y
    sx = swing.rect.x + swing.rect.width / 2
    if abs(c0 - sx) >= abs(c1 - sx):
        hx, hy = c0, cy
        hinge_at_low = True
    else:
        hx, hy = c1, cy
        hinge_at_low = False
    swing_south = (swing.rect.y + swing.rect.depth / 2) > cy
    if swing_south:
        # 面北：left=西(low x), right=东(high x)
        hinge_side = "left" if hinge_at_low else "right"
    else:
        # 面南：left=东(high), right=西(low)
        hinge_side = "right" if hinge_at_low else "left"
    return cx, cy, hx, hy, hinge_side


def build_door_opening(
    conn: SpaceConnection,
    pa: RoomPlacement,
    pb: RoomPlacement,
    boundary: SharedBoundary,
    *,
    door_width: float = DEFAULT_DOOR_WIDTH,
) -> DoorOpening:
    """由共边构造带 polish 字段的 DoorOpening（不改房间）。"""
    is_open = conn.type == SpaceConnectionType.OPEN
    width = min(door_width, max(MIN_CLEAR_WIDTH, boundary.length * 0.5))
    width = min(width, boundary.length)

    if is_open:
        return DoorOpening(
            id=f"door-{conn.id}",
            connection_id=conn.id,
            room_a_id=conn.a,
            room_b_id=conn.b,
            floor_id=boundary.floor_id,
            x=boundary.mid_x,
            y=boundary.mid_y,
            width=min(boundary.length, max(width, boundary.length * 0.6)),
            axis=boundary.axis,  # type: ignore[arg-type]
            connection_type=conn.type.value,
            clear_width=min(boundary.length, max(width, boundary.length * 0.6)),
            swing_room_id=None,
            hinge_side=None,
            hinge_x=None,
            hinge_y=None,
        )

    swing = choose_swing_room(pa, pb)
    cx, cy, hx, hy, hinge_side = _hinge_geometry(
        boundary, swing, door_width=width
    )

    return DoorOpening(
        id=f"door-{conn.id}",
        connection_id=conn.id,
        room_a_id=conn.a,
        room_b_id=conn.b,
        floor_id=boundary.floor_id,
        x=cx,
        y=cy,
        width=width,
        axis=boundary.axis,  # type: ignore[arg-type]
        connection_type=conn.type.value,
        clear_width=width,
        swing_room_id=swing.room_id,
        hinge_side=hinge_side,
        hinge_x=hx,
        hinge_y=hy,
    )


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def place_door_openings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    min_length: float = MIN_ACCESS_WALL,
    door_width: float = DEFAULT_DOOR_WIDTH,
) -> list[DoorOpening]:
    """
    为所有几何可实现的开口类 Intent（含 soft）标注 DoorOpening，
    并在同层共墙连通分量上补 spanning-tree OPEN（显式开口，≠ 自动 PASSAGE）。

    required 无法实现 → checker hard；soft 无法实现 → soft penalty。
    **不修改** floors/placements。
    """
    from solver.topology.derive_access import ensure_access_graph

    ensure_access_graph(program)
    openings: list[DoorOpening] = []
    seen_pairs: set[tuple[str, str]] = set()
    program_ids = {r.id for r in program.rooms}
    entry = candidate.exterior_entry
    entry_rooms = set(entry.connected_room_ids) if entry is not None else set()
    floor_ctx: dict[str, _FloorGraphContext] = {}
    for fl in candidate.floors:
        ctx = _build_floor_graph_context(
            program,
            candidate,
            fl,
            program_ids=program_ids,
            entry_rooms=entry_rooms,
            min_length=min_length,
        )
        if ctx is not None:
            floor_ctx[fl.floor_id] = ctx

    for conn in opening_connections(program):
        pas = find_placements(candidate, conn.a)
        pbs = find_placements(candidate, conn.b)
        paired: tuple[RoomPlacement, RoomPlacement, SharedBoundary] | None = None
        for pa in pas:
            for pb in pbs:
                boundary = shared_boundary_between(pa, pb, min_length=min_length)
                if boundary is not None:
                    paired = (pa, pb, boundary)
                    break
            if paired is not None:
                break
        if paired is None:
            continue
        pa, pb, boundary = paired
        opening = build_door_opening(conn, pa, pb, boundary, door_width=door_width)
        openings.append(opening)
        seen_pairs.add(_pair_key(pa.room_id, pb.room_id))

    intents = opening_connections(program)
    privacy_plans = {
        floor_id: _plan_joint_privacy_edges(ctx, openings, intents, seen_pairs)
        for floor_id, ctx in floor_ctx.items()
    }
    openings = _apply_joint_privacy_plans(openings, floor_ctx, privacy_plans)
    seen_pairs = {_pair_key(op.room_a_id, op.room_b_id) for op in openings}

    openings.extend(
        _spanning_tree_open_openings(
            program,
            candidate,
            seen_pairs=seen_pairs,
            min_length=min_length,
            prior_openings=openings,
            privacy_plans=privacy_plans,
        )
    )
    candidate.door_openings = openings
    return openings


@dataclass(frozen=True)
class _FloorGraphContext:
    adj: dict[str, list[str]]
    by_id: dict[str, RoomPlacement]
    anchors: list[str]
    ids: list[str]
    edge_bound: dict[tuple[str, str], SharedBoundary]


def _build_floor_graph_context(
    program: DesignProgram,
    candidate: LayoutCandidate,
    floor,
    *,
    program_ids: set[str],
    entry_rooms: set[str],
    min_length: float,
) -> _FloorGraphContext | None:
    """同层 program 房间共墙全邻接图（含 private-private）。"""
    from collections import defaultdict

    rooms = [
        p
        for p in floor.placements
        if p.room_id in program_ids and not p.room_id.startswith("stair-")
    ]
    if len(rooms) < 2:
        return None
    by_id = {p.room_id: p for p in rooms}
    adj: dict[str, list[str]] = defaultdict(list)
    edge_bound: dict[tuple[str, str], SharedBoundary] = {}
    ids = sorted(by_id)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            bound = shared_boundary_between(
                by_id[a], by_id[b], min_length=min_length
            )
            if bound is None:
                continue
            adj[a].append(b)
            adj[b].append(a)
            edge_bound[_pair_key(a, b)] = bound

    anchors = [rid for rid in ids if rid in entry_rooms]
    if not anchors:
        stairs = [
            p
            for p in floor.placements
            if p.room_id.startswith("stair-")
            or (
                (p.category or "") == "circulation"
                and "楼梯" in (p.name or "")
            )
        ]
        for s in stairs:
            for rid in ids:
                if shared_boundary_between(s, by_id[rid], min_length=min_length):
                    anchors.append(rid)
    if not anchors:
        anchors = [ids[0]]

    return _FloorGraphContext(
        adj=dict(adj),
        by_id=by_id,
        anchors=anchors,
        ids=ids,
        edge_bound=edge_bound,
    )


def _apply_joint_privacy_plans(
    openings: list[DoorOpening],
    floor_ctx: dict[str, _FloorGraphContext],
    privacy_plans: dict[str, _JointPrivacyPlan],
) -> list[DoorOpening]:
    """按联合隐私计划裁剪 intent 门并打 forced 标记。"""
    kept: list[DoorOpening] = []
    for op in openings:
        key = _pair_key(op.room_a_id, op.room_b_id)
        plan = privacy_plans.get(op.floor_id)
        ctx = floor_ctx.get(op.floor_id)
        if plan is None or ctx is None:
            kept.append(op)
            continue
        pa = ctx.by_id.get(op.room_a_id)
        pb = ctx.by_id.get(op.room_b_id)
        if (
            pa is not None
            and pb is not None
            and _private_private_pair(pa, pb)
            and key in plan.omit_pp_keys
        ):
            continue
        updates: dict[str, bool] = {}
        if key in plan.forced_pp_keys:
            updates["forced_private_adjacency"] = True
        if key in plan.forced_wet_keys:
            updates["forced_wet_private_fanout"] = True
        if updates:
            kept.append(op.model_copy(update=updates))
        else:
            kept.append(op)
    return kept


def _prune_removable_private_private_openings(
    openings: list[DoorOpening],
    floor_ctx: dict[str, _FloorGraphContext],
    intents: list[SpaceConnection],
    *,
    seen_pairs: set[tuple[str, str]],
) -> list[DoorOpening]:
    """移除有替代路径的私密-私密 intent 门；保留被迫桥接并打 forced 标记。"""
    required_pp: set[tuple[str, str]] = set()
    for conn in intents:
        if conn.required:
            required_pp.add(_pair_key(conn.a, conn.b))

    pruned: list[DoorOpening] = []
    for op in openings:
        key = _pair_key(op.room_a_id, op.room_b_id)
        if key in required_pp:
            pruned.append(op)
            continue
        ctx = floor_ctx.get(op.floor_id)
        if ctx is None:
            pruned.append(op)
            continue
        pa = ctx.by_id.get(op.room_a_id)
        pb = ctx.by_id.get(op.room_b_id)
        if pa is None or pb is None or not _private_private_pair(pa, pb):
            pruned.append(op)
            continue
        if _private_private_is_forced_bridge(pa, pb, ctx, openings, seen_pairs):
            pruned.append(
                op.model_copy(update={"forced_private_adjacency": True})
            )
            continue
        # 可绕开：不落门，由 spanning tree 负责连通
    return pruned


def _private_private_is_forced_bridge(
    pa: RoomPlacement,
    pb: RoomPlacement,
    ctx: _FloorGraphContext,
    openings: list[DoorOpening],
    seen_pairs: set[tuple[str, str]],
) -> bool:
    """移除该私密-私密 intent 后，spanning 无法覆盖全层 → 被迫保留。"""
    key = _pair_key(pa.room_id, pb.room_id)
    trial_seen = seen_pairs - {key}
    trial_openings = [
        op
        for op in openings
        if _pair_key(op.room_a_id, op.room_b_id) != key
    ]
    return not _planned_access_covers_floor(ctx, trial_openings, trial_seen)


def _reachable_from_anchors(
    adj: dict[str, list[str]],
    node_set: set[str],
    anchors: list[str],
    *,
    excluded_edges: set[tuple[str, str]] = frozenset(),
) -> set[str]:
    """从锚点集合在 node_set 内可达的房间（可排除指定边）。"""
    from collections import deque

    visited: set[str] = set()
    for start in anchors:
        if start not in node_set:
            continue
        q: deque[str] = deque([start])
        visited.add(start)
        while q:
            cur = q.popleft()
            for nb in adj.get(cur, []):
                if nb not in node_set or nb in visited:
                    continue
                if _pair_key(cur, nb) in excluded_edges:
                    continue
                visited.add(nb)
                q.append(nb)
    return visited


def _is_private_bridge_edge(
    a: str,
    b: str,
    adj: dict[str, list[str]],
    node_set: set[str],
    anchors: list[str],
) -> bool:
    """移除该边后锚点无法覆盖全部房间 → 桥（被迫保留私密-私密开口）。"""
    key = _pair_key(a, b)
    without = _reachable_from_anchors(
        adj, node_set, anchors, excluded_edges={key}
    )
    return without != node_set


def _compute_spanning_tree_edge_keys(
    adj: dict[str, list[str]],
    by_id: dict[str, RoomPlacement],
    anchors: list[str],
    ids: list[str],
    wet_private: dict[str, set[str]],
    *,
    omit_pp_keys: set[tuple[str, str]],
    seen_pairs: set[tuple[str, str]],
    blocked_wet_keys: set[tuple[str, str]] | None = None,
    forced_wet_keys: set[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """BFS 生成树边（pair_key），跳过 omit_pp 与 wet 扇出超限。"""
    from collections import deque

    blocked_wet = blocked_wet_keys or set()
    forced_wet = forced_wet_keys or set()
    node_set = set(ids)
    visited: set[str] = set()
    tree_keys: list[tuple[str, str]] = []
    wet_work = {k: set(v) for k, v in wet_private.items()}

    for start in anchors:
        if start in visited or start not in by_id:
            continue
        q: deque[str] = deque([start])
        visited.add(start)
        while q:
            cur = q.popleft()
            for nb in sorted(adj.get(cur, [])):
                if nb in visited or nb not in node_set:
                    continue
                key = _pair_key(cur, nb)
                if key in omit_pp_keys:
                    continue
                if key in seen_pairs:
                    visited.add(nb)
                    q.append(nb)
                    continue
                pa, pb = by_id[cur], by_id[nb]
                if not _spanning_wet_edge_allowed(
                    pa,
                    pb,
                    key,
                    wet_work,
                    forced_wet_keys=forced_wet,
                    blocked_wet_keys=blocked_wet,
                ):
                    continue
                visited.add(nb)
                q.append(nb)
                tree_keys.append(key)
                _record_wet_private_pair(pa, pb, wet_work)
    return tree_keys


def _plan_private_private_span_edges(
    adj: dict[str, list[str]],
    by_id: dict[str, RoomPlacement],
    anchors: list[str],
    ids: list[str],
    wet_private_base: dict[str, set[str]],
    *,
    seen_pairs: set[tuple[str, str]],
    omit_pp_keys: set[tuple[str, str]] | None = None,
    blocked_wet_keys: set[tuple[str, str]] | None = None,
    forced_wet_keys: set[tuple[str, str]] | None = None,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """
    迭代排除可绕开的私密-私密生成树边；返回 (最终树边 keys, forced 边 keys)。
    """
    node_set = set(ids)
    omit_pp = set(omit_pp_keys or ())
    blocked_wet = blocked_wet_keys or set()
    forced_wet = forced_wet_keys or set()
    excluded_pp: set[tuple[str, str]] = set(omit_pp)

    def _wet_work() -> dict[str, set[str]]:
        return {k: set(v) for k, v in wet_private_base.items()}

    while True:
        tree_keys = _compute_spanning_tree_edge_keys(
            adj,
            by_id,
            anchors,
            ids,
            _wet_work(),
            omit_pp_keys=excluded_pp,
            seen_pairs=seen_pairs,
            blocked_wet_keys=blocked_wet,
            forced_wet_keys=forced_wet,
        )
        removable: set[tuple[str, str]] = set()
        for key in tree_keys:
            pa = by_id[key[0]]
            pb = by_id[key[1]]
            if not _private_private_pair(pa, pb):
                continue
            trial_excluded = excluded_pp | {key}
            trial_tree = _compute_spanning_tree_edge_keys(
                adj,
                by_id,
                anchors,
                ids,
                _wet_work(),
                omit_pp_keys=trial_excluded,
                seen_pairs=seen_pairs,
                blocked_wet_keys=blocked_wet,
                forced_wet_keys=forced_wet,
            )
            trial_visited = _spanning_visit_set(
                adj,
                by_id,
                anchors,
                ids,
                wet_private_base,
                excluded_edges=trial_excluded,
                seen_pairs=seen_pairs | set(trial_tree),
                forced_wet_keys=forced_wet,
                blocked_wet_keys=blocked_wet,
            )
            if trial_visited == node_set:
                removable.add(key)
        if not removable:
            break
        excluded_pp |= removable

    final_keys = _compute_spanning_tree_edge_keys(
        adj,
        by_id,
        anchors,
        ids,
        _wet_work(),
        omit_pp_keys=excluded_pp,
        seen_pairs=seen_pairs,
        blocked_wet_keys=blocked_wet,
        forced_wet_keys=forced_wet,
    )
    forced_keys: set[tuple[str, str]] = set()
    for key in final_keys:
        pa = by_id[key[0]]
        pb = by_id[key[1]]
        if _private_private_pair(pa, pb):
            forced_keys.add(key)
    return set(final_keys), forced_keys


def _spanning_tree_open_openings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    seen_pairs: set[tuple[str, str]],
    min_length: float,
    prior_openings: list[DoorOpening],
    privacy_plans: dict[str, _JointPrivacyPlan] | None = None,
) -> list[DoorOpening]:
    """
    同层 program 房间共墙图 → 从入口/楼梯锚点 BFS 生成树 → OPEN 开口。

    共墙本身仍不可通行；这里显式生成开口，使连通分量可导航。
    """
    program_ids = {r.id for r in program.rooms}
    out: list[DoorOpening] = []

    entry = candidate.exterior_entry
    entry_rooms = set(entry.connected_room_ids) if entry is not None else set()

    for fl in candidate.floors:
        ctx = _build_floor_graph_context(
            program,
            candidate,
            fl,
            program_ids=program_ids,
            entry_rooms=entry_rooms,
            min_length=min_length,
        )
        if ctx is None:
            continue
        by_id = ctx.by_id
        adj = ctx.adj
        edge_bound = ctx.edge_bound
        ids = ctx.ids
        anchors = ctx.anchors
        wet_private = _wet_private_neighbor_map(prior_openings, by_id)
        plan = (privacy_plans or {}).get(fl.floor_id, _JointPrivacyPlan(set(), set(), set(), set()))

        tree_keys, forced_pp_keys = _plan_private_private_span_edges(
            adj,
            by_id,
            anchors,
            ids,
            wet_private,
            seen_pairs=seen_pairs,
            omit_pp_keys=plan.omit_pp_keys,
            blocked_wet_keys=plan.blocked_wet_keys,
            forced_wet_keys=plan.forced_wet_keys,
        )

        for key in sorted(tree_keys):
            if key in seen_pairs:
                continue
            bound = edge_bound.get(key)
            if bound is None:
                continue
            seen_pairs.add(key)
            forced_pp = key in forced_pp_keys
            forced_wet = key in plan.forced_wet_keys
            width = min(bound.length, max(PREFERRED_CLEAR_WIDTH, bound.length * 0.5))
            out.append(
                DoorOpening(
                    id=f"open-span-{key[0]}-{key[1]}",
                    connection_id=f"span-{key[0]}-{key[1]}",
                    room_a_id=key[0],
                    room_b_id=key[1],
                    floor_id=fl.floor_id,
                    x=bound.mid_x,
                    y=bound.mid_y,
                    width=width,
                    axis=bound.axis,  # type: ignore[arg-type]
                    connection_type=SpaceConnectionType.OPEN.value,
                    clear_width=width,
                    swing_room_id=None,
                    hinge_side=None,
                    hinge_x=None,
                    hinge_y=None,
                    forced_private_adjacency=forced_pp,
                    forced_wet_private_fanout=forced_wet,
                )
            )
    return out


def door_clear_width_violations(
    candidate: LayoutCandidate,
    *,
    preferred_clear: float = PREFERRED_CLEAR_WIDTH,
    physical_min: float = PHYSICAL_MIN_WIDTH,
) -> list:
    """净宽：< physical_min soft 偏硬警告；< preferred soft。"""
    from packages.schema.layout import Violation

    viols: list[Violation] = []
    for op in candidate.door_openings:
        if op.connection_type == SpaceConnectionType.OPEN.value:
            continue
        clear = op.clear_width if op.clear_width is not None else op.width
        if clear + 1e-9 < physical_min:
            viols.append(
                Violation(
                    constraint_id="door.physical_min_width",
                    room_ids=[op.room_a_id, op.room_b_id],
                    message=(
                        f"门洞物理宽度 {clear:.2f}m < {physical_min:.2f}m "
                        f"({op.room_a_id}—{op.room_b_id})"
                    ),
                    measured_value=clear,
                    required_value=physical_min,
                    hard=False,
                    source="system",
                )
            )
        elif clear + 1e-9 < preferred_clear:
            viols.append(
                Violation(
                    constraint_id="door.clear_width",
                    room_ids=[op.room_a_id, op.room_b_id],
                    message=(
                        f"门洞净宽 {clear:.2f}m < 偏好 {preferred_clear:.2f}m "
                        f"({op.room_a_id}—{op.room_b_id})"
                    ),
                    measured_value=clear,
                    required_value=preferred_clear,
                    hard=False,
                    source="system",
                )
            )
    return viols


def preferred_blocked_violations(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    min_length: float = MIN_ACCESS_WALL,
) -> list:
    """soft AccessIntent 无法实现 → soft violation。"""
    from packages.schema.layout import Violation

    viols: list[Violation] = []
    for conn, measured in missing_shared_boundaries(
        program, candidate, min_length=min_length, only_required=False
    ):
        if conn.required:
            continue
        viols.append(
            Violation(
                constraint_id="access.preferred_blocked",
                room_ids=[conn.a, conn.b],
                message=(
                    f"偏好通行 {conn.a}—{conn.b}（{conn.type.value}）"
                    f"未实现共边/开口"
                ),
                measured_value=measured,
                required_value=min_length,
                hard=False,
                source="system",
            )
        )
    return viols

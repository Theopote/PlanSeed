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
from solver.topology.access import MIN_ACCESS_WALL

# 需要同层共边才能落开口的连接类型（楼梯 / 入口另议）
_OPENING_TYPES = frozenset(
    {
        SpaceConnectionType.OPEN,
        SpaceConnectionType.DOOR,
        SpaceConnectionType.PASSAGE,
    }
)

DEFAULT_DOOR_WIDTH = 0.9
MIN_CLEAR_WIDTH = 0.8
MIN_WALL_REVEAL = 0.05  # 洞口距共边端头的最小留墙


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


def required_opening_connections(program: DesignProgram) -> list[SpaceConnection]:
    if program.access_graph is None:
        return []
    return [
        c
        for c in program.access_graph.required_connections()
        if c.type in _OPENING_TYPES
    ]


def missing_shared_boundaries(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    min_length: float = MIN_ACCESS_WALL,
) -> list[tuple[SpaceConnection, float]]:
    """
    返回 (connection, measured_shared_length) 列表：required 开口连接缺少足够共边。
    measured 为实际共边（可能为 0）。
    """
    missing: list[tuple[SpaceConnection, float]] = []
    for conn in required_opening_connections(program):
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


def place_door_openings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    min_length: float = MIN_ACCESS_WALL,
    door_width: float = DEFAULT_DOOR_WIDTH,
) -> list[DoorOpening]:
    """
    在已有共边上标注 DoorOpening（含 2.2 polish）；**不修改** floors/placements。

    无足够共边的 required 连接不生成开口（由 checker 判 invalid）。
    """
    openings: list[DoorOpening] = []
    for conn in required_opening_connections(program):
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
        openings.append(
            build_door_opening(
                conn, pa, pb, boundary, door_width=door_width
            )
        )
    candidate.door_openings = openings
    return openings


def door_clear_width_violations(
    candidate: LayoutCandidate,
    *,
    min_clear: float = MIN_CLEAR_WIDTH,
) -> list:
    """净宽不足 → soft Violation 列表（不改几何）。"""
    from packages.schema.layout import Violation

    viols: list[Violation] = []
    for op in candidate.door_openings:
        if op.connection_type == SpaceConnectionType.OPEN.value:
            continue
        clear = op.clear_width if op.clear_width is not None else op.width
        if clear + 1e-9 < min_clear:
            viols.append(
                Violation(
                    constraint_id="door.clear_width",
                    room_ids=[op.room_a_id, op.room_b_id],
                    message=(
                        f"门洞净宽 {clear:.2f}m < {min_clear:.2f}m "
                        f"({op.room_a_id}—{op.room_b_id})"
                    ),
                    measured_value=clear,
                    required_value=min_clear,
                    hard=False,
                    source="system",
                )
            )
    return viols

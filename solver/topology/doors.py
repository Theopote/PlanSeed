"""
Phase 2A — 门洞标注：geometry → topology validation。

原则：
- **禁止**为放门回改 / 重优化 RoomPlacement
- 仅检查 required SpaceConnection 是否有足够共边
- 有共边 → 在边界上标注 DoorOpening；无共边 → hard invalid
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class SharedBoundary:
    floor_id: str
    length: float
    axis: str  # "x" | "y"
    mid_x: float
    mid_y: float


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


def place_door_openings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    min_length: float = MIN_ACCESS_WALL,
    door_width: float = 0.9,
) -> list[DoorOpening]:
    """
    在已有共边上标注 DoorOpening；**不修改** floors/placements。

    无足够共边的 required 连接不生成开口（由 checker 判 invalid）。
    """
    openings: list[DoorOpening] = []
    for conn in required_opening_connections(program):
        pas = find_placements(candidate, conn.a)
        pbs = find_placements(candidate, conn.b)
        boundary: SharedBoundary | None = None
        for pa in pas:
            for pb in pbs:
                boundary = shared_boundary_between(pa, pb, min_length=min_length)
                if boundary is not None:
                    break
            if boundary is not None:
                break
        if boundary is None:
            continue
        width = min(door_width, max(min_length, boundary.length * 0.5))
        openings.append(
            DoorOpening(
                id=f"door-{conn.id}",
                connection_id=conn.id,
                room_a_id=conn.a,
                room_b_id=conn.b,
                floor_id=boundary.floor_id,
                x=boundary.mid_x,
                y=boundary.mid_y,
                width=width,
                axis=boundary.axis,  # type: ignore[arg-type]
                connection_type=conn.type.value,
            )
        )
    candidate.door_openings = openings
    return openings

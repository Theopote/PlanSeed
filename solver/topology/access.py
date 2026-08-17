"""
Realized Circulation — Phase 2.3。

原则：
  Adjacency / 共墙 ≠ Access Intent ≠ Realized Access
  Reachability BFS 只走 RealizedAccessGraph（门/开口/入口/楼梯核）。
"""

from __future__ import annotations

from collections import defaultdict, deque

from packages.schema.layout import LayoutCandidate, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.topology import (
    AccessGraph,
    ConnectionState,
    ConnectionStatus,
    RealizedConnection,
    SpaceConnection,
    SpaceConnectionType,
)
from solver.geometry.rect import from_placement, shared_edge_length
from solver.topology.constants import ENTRY_NODE_ID, MIN_ACCESS_WALL, MIN_MEANINGFUL_CORRIDOR_SHORT

# 兼容旧 import 路径
__all__ = [
    "ENTRY_NODE_ID",
    "MIN_ACCESS_WALL",
    "access_depths",
    "build_realized_access_graph",
    "build_realized_connections",
    "evaluate_connection_statuses",
    "occupied_room_ids",
    "reachable_nodes",
    "realized_to_access_graph",
    "unreachable_occupied_rooms",
]


def occupied_room_ids(program: DesignProgram) -> set[str]:
    return {r.id for r in program.rooms}


def _add_stair_realized(candidate: LayoutCandidate) -> list[RealizedConnection]:
    """跨层对齐楼梯核 → realized STAIR（非共墙）。"""
    out: list[RealizedConnection] = []
    by_floor: dict[str, list[RoomPlacement]] = {}
    for fl in candidate.floors:
        by_floor[fl.floor_id] = [
            p
            for p in fl.placements
            if p.category == "circulation" or p.room_id.startswith("stair-")
        ]
    floor_ids = [fl.floor_id for fl in candidate.floors]
    for i in range(len(floor_ids) - 1):
        fa, fb = floor_ids[i], floor_ids[i + 1]
        for pa in by_floor.get(fa, []):
            for pb in by_floor.get(fb, []):
                if abs(pa.rect.x - pb.rect.x) > 0.05:
                    continue
                if abs(pa.rect.y - pb.rect.y) > 0.05:
                    continue
                if abs(pa.rect.width - pb.rect.width) > 0.05:
                    continue
                if abs(pa.rect.depth - pb.rect.depth) > 0.05:
                    continue
                out.append(
                    RealizedConnection(
                        connection_id=f"stair-{pa.room_id}-{pb.room_id}",
                        a=pa.room_id,
                        b=pb.room_id,
                        type=SpaceConnectionType.STAIR,
                        floor_id=None,
                        opening_id=None,
                        source="stair",
                    )
                )
    return out


def _add_stair_access_realized(
    candidate: LayoutCandidate,
) -> list[RealizedConnection]:
    """
    楼梯核与贴邻房间：基础设施开口（≠ 普通房间共墙自动通行）。

    竖向核必须可从同层贴边房间进入，否则跨层 Realized 图断裂。
    """
    from solver.topology.doors import shared_boundary_between

    out: list[RealizedConnection] = []
    for fl in candidate.floors:
        stairs = [
            p
            for p in fl.placements
            if p.room_id.startswith("stair-")
            or (
                (p.category or "") == "circulation"
                and "楼梯" in (p.name or "")
            )
        ]
        rooms = [p for p in fl.placements if p not in stairs]
        for s in stairs:
            for r in rooms:
                if shared_boundary_between(s, r, min_length=MIN_ACCESS_WALL) is None:
                    continue
                pair = tuple(sorted((s.room_id, r.room_id)))
                out.append(
                    RealizedConnection(
                        connection_id=f"stair-access-{pair[0]}-{pair[1]}",
                        a=s.room_id,
                        b=r.room_id,
                        type=SpaceConnectionType.PASSAGE,
                        floor_id=fl.floor_id,
                        opening_id=None,
                        source="stair_access",
                    )
                )
    return out


def _add_circulation_corridor_passages(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    min_length: float = MIN_ACCESS_WALL,
) -> list[RealizedConnection]:
    """
    generated 走廊碎片与贴邻 program 房间：基础设施开口（同楼梯贴邻 PASSAGE）。

    使 ADR-011 几何修补切出的 circ-* 真正进入 RealizedAccessGraph，
    卧室可经走廊到达，而非被迫穿其他卧室。
    """
    from solver.topology.doors import shared_boundary_between

    program_ids = {r.id for r in program.rooms}
    out: list[RealizedConnection] = []
    seen: set[tuple[str, str]] = set()
    for fl in candidate.floors:
        corridors = [
            p
            for p in fl.placements
            if p.room_id.startswith("circ-")
            and (p.category or "") == "circulation"
        ]
        rooms = [p for p in fl.placements if p.room_id in program_ids]
        for circ in corridors:
            short = min(circ.rect.width, circ.rect.depth)
            if short + 1e-9 < MIN_MEANINGFUL_CORRIDOR_SHORT:
                continue
            for room in rooms:
                if shared_boundary_between(circ, room, min_length=min_length) is None:
                    continue
                pair = tuple(sorted((circ.room_id, room.room_id)))
                if pair in seen:
                    continue
                seen.add(pair)
                out.append(
                    RealizedConnection(
                        connection_id=f"circ-passage-{pair[0]}-{pair[1]}",
                        a=pair[0],
                        b=pair[1],
                        type=SpaceConnectionType.PASSAGE,
                        floor_id=fl.floor_id,
                        opening_id=None,
                        source="circulation_passage",
                    )
                )
    return out


def build_realized_connections(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[RealizedConnection]:
    """
    汇总已实现通行边：ExteriorEntry、DoorOpening、Stair 竖向、楼梯贴邻。

    **禁止**把普通房间共墙自动变成 PASSAGE。
    """
    from solver.circulation.exterior_entry import resolve_exterior_entry

    realized: list[RealizedConnection] = []

    entry = candidate.exterior_entry
    if entry is None:
        entry = resolve_exterior_entry(program, candidate)
        candidate.exterior_entry = entry

    targets = list(entry.connected_room_ids)
    non_stair = [r for r in targets if not str(r).startswith("stair-")]
    use = non_stair if non_stair else targets
    for rid in use:
        realized.append(
            RealizedConnection(
                connection_id=f"ext-entry-{rid}",
                a=entry.id,
                b=rid,
                type=SpaceConnectionType.EXTERIOR_ENTRY,
                floor_id=entry.floor_id,
                opening_id=None,
                source="exterior_entry",
            )
        )

    for op in candidate.door_openings:
        try:
            ctype = SpaceConnectionType(op.connection_type)
        except ValueError:
            ctype = SpaceConnectionType.DOOR
        realized.append(
            RealizedConnection(
                connection_id=op.connection_id,
                a=op.room_a_id,
                b=op.room_b_id,
                type=ctype,
                floor_id=op.floor_id,
                opening_id=op.id,
                source="opening",
            )
        )

    realized.extend(_add_stair_realized(candidate))
    realized.extend(_add_stair_access_realized(candidate))
    realized.extend(_add_circulation_corridor_passages(program, candidate))
    candidate.realized_connections = list(realized)
    return realized


def realized_to_access_graph(realized: list[RealizedConnection]) -> AccessGraph:
    graph = AccessGraph()
    for rc in realized:
        graph.add_connection(
            SpaceConnection(
                id=rc.connection_id or f"{rc.a}-{rc.b}",
                a=rc.a,
                b=rc.b,
                type=rc.type,
                required=True,
                description=f"realized:{rc.source}",
            )
        )
    return graph


def build_realized_access_graph(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> AccessGraph:
    """RealizedAccessGraph — 仅已实现通行边。"""
    return realized_to_access_graph(build_realized_connections(program, candidate))


def evaluate_connection_statuses(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[ConnectionStatus]:
    """为每条开口类 AccessIntent 标注 INTENDED/FEASIBLE/REALIZED/BLOCKED。"""
    from solver.topology.derive_access import ensure_access_graph
    from solver.topology.doors import (
        find_placements,
        opening_connections,
        shared_boundary_between,
    )

    ensure_access_graph(program)
    opening_ids = {op.connection_id for op in candidate.door_openings if op.connection_id}
    statuses: list[ConnectionStatus] = []
    for conn in opening_connections(program):
        pas = find_placements(candidate, conn.a)
        pbs = find_placements(candidate, conn.b)
        shared = 0.0
        feasible = False
        for pa in pas:
            for pb in pbs:
                if pa.floor_id != pb.floor_id:
                    continue
                length = shared_edge_length(
                    from_placement(pa.rect), from_placement(pb.rect)
                )
                shared = max(shared, length)
                if shared_boundary_between(pa, pb, min_length=MIN_ACCESS_WALL):
                    feasible = True
        if conn.id in opening_ids:
            state = ConnectionState.REALIZED
            oid = next(
                (
                    op.id
                    for op in candidate.door_openings
                    if op.connection_id == conn.id
                ),
                None,
            )
        elif feasible:
            state = ConnectionState.FEASIBLE
            oid = None
        else:
            state = ConnectionState.BLOCKED
            oid = None
        statuses.append(
            ConnectionStatus(
                connection_id=conn.id,
                a=conn.a,
                b=conn.b,
                type=conn.type,
                required=conn.required,
                state=state,
                opening_id=oid,
                shared_length=shared if shared > 0 else None,
            )
        )
    return statuses


def reachable_nodes(graph: AccessGraph, *, start: str = ENTRY_NODE_ID) -> set[str]:
    adj: dict[str, set[str]] = defaultdict(set)
    for c in graph.connections:
        if c.a == c.b:
            continue
        adj[c.a].add(c.b)
        adj[c.b].add(c.a)

    if start not in adj and start not in graph.node_ids:
        return set()

    seen: set[str] = {start}
    q: deque[str] = deque([start])
    while q:
        cur = q.popleft()
        for nb in adj.get(cur, ()):
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    return seen


def access_depths(
    graph: AccessGraph, *, start: str = ENTRY_NODE_ID
) -> dict[str, int]:
    """从 Entry 的 BFS 深度（仅 realized）。"""
    adj: dict[str, set[str]] = defaultdict(set)
    for c in graph.connections:
        if c.a == c.b:
            continue
        adj[c.a].add(c.b)
        adj[c.b].add(c.a)
    if start not in adj and start not in graph.node_ids:
        return {}
    depth = {start: 0}
    q: deque[str] = deque([start])
    while q:
        cur = q.popleft()
        for nb in adj.get(cur, ()):
            if nb not in depth:
                depth[nb] = depth[cur] + 1
                q.append(nb)
    return depth


def unreachable_occupied_rooms(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[str]:
    """从 Entry 经 RealizedAccessGraph 不可达的 occupied room。"""
    occupied = occupied_room_ids(program)
    if not occupied or not candidate.floors:
        return []

    graph = build_realized_access_graph(program, candidate)
    has_entry = any(
        c.type == SpaceConnectionType.EXTERIOR_ENTRY and ENTRY_NODE_ID in (c.a, c.b)
        for c in graph.connections
    )
    if not has_entry:
        return sorted(occupied)

    reached = reachable_nodes(graph, start=ENTRY_NODE_ID)
    return sorted(occupied - reached)

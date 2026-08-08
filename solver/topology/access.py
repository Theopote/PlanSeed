"""
AccessGraph 可达性 — Phase 2.1 第一硬规则。

原则：所有 occupied space 必须从 ExteriorEntry（≠ Stair）可达。
"""

from __future__ import annotations

from collections import defaultdict, deque

from packages.schema.layout import LayoutCandidate, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.topology import (
    AccessGraph,
    SpaceConnection,
    SpaceConnectionType,
)
from solver.geometry.rect import from_placement, shared_edge_length

ENTRY_NODE_ID = "exterior-entry"  # ExteriorEntry.id；≠ stair
MIN_ACCESS_WALL = 0.9  # 可通行开口最小共边（米）


def occupied_room_ids(program: DesignProgram) -> set[str]:
    """须从入口可达的占用空间（程序房间，不含仅 generated 的核）。"""
    return {r.id for r in program.rooms}


def build_realized_access_graph(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> AccessGraph:
    """
    构造用于可达性检查的 AccessGraph。

    起点：ExteriorEntry（≠ Stair）。
    边：program.access_graph + 入口→厅/门厅 + 共边 PASSAGE + 楼梯 STAIR。
    """
    from solver.circulation.exterior_entry import resolve_exterior_entry

    graph = AccessGraph()
    if program.access_graph is not None:
        for c in program.access_graph.connections:
            graph.add_connection(c)
        for nid in program.access_graph.node_ids:
            if nid not in graph.node_ids:
                graph.node_ids.append(nid)

    entry = candidate.exterior_entry
    if entry is None:
        entry = resolve_exterior_entry(program, candidate)
        candidate.exterior_entry = entry

    if entry.id not in graph.node_ids:
        graph.node_ids.append(entry.id)

    _add_exterior_entry_edges(entry, graph)
    _add_shared_boundary_edges(candidate, graph)
    _add_stair_edges(candidate, graph)
    return graph


def _add_exterior_entry_edges(entry, graph: AccessGraph) -> None:
    """
    ExteriorEntry → 贴边房间。

    connected_room_ids 已按「非楼梯优先」排序；若全是楼梯才连楼梯（回退）。
    """
    targets = list(entry.connected_room_ids)
    non_stair = [r for r in targets if not str(r).startswith("stair-")]
    use = non_stair if non_stair else targets
    for rid in use:
        graph.add_connection(
            SpaceConnection(
                id=f"ext-entry-{rid}",
                a=entry.id,
                b=rid,
                type=SpaceConnectionType.EXTERIOR_ENTRY,
                required=True,
                description="ExteriorEntry → 室内首达空间",
            )
        )


def _add_shared_boundary_edges(
    candidate: LayoutCandidate, graph: AccessGraph
) -> None:
    for fl in candidate.floors:
        placements = fl.placements
        for i, a in enumerate(placements):
            ra = from_placement(a.rect)
            for b in placements[i + 1 :]:
                shared = shared_edge_length(ra, from_placement(b.rect))
                if shared + 1e-9 < MIN_ACCESS_WALL:
                    continue
                pair = tuple(sorted((a.room_id, b.room_id)))
                graph.add_connection(
                    SpaceConnection(
                        id=f"pass-{pair[0]}-{pair[1]}",
                        a=pair[0],
                        b=pair[1],
                        type=SpaceConnectionType.PASSAGE,
                        required=True,
                        description=f"共边 {shared:.2f}m",
                    )
                )


def _add_stair_edges(candidate: LayoutCandidate, graph: AccessGraph) -> None:
    """跨层楼梯核：同名 stair-* 或均为 circulation 且 AABB 对齐。"""
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
                graph.add_connection(
                    SpaceConnection(
                        id=f"stair-{pa.room_id}-{pb.room_id}",
                        a=pa.room_id,
                        b=pb.room_id,
                        type=SpaceConnectionType.STAIR,
                        required=True,
                        description="楼梯核跨层",
                    )
                )


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


def unreachable_occupied_rooms(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[str]:
    """返回从 Entry 不可达的 occupied room_id（排序稳定）。"""
    occupied = occupied_room_ids(program)
    if not occupied or not candidate.floors:
        return []

    graph = build_realized_access_graph(program, candidate)
    # 无任何入口边 → 全部 occupied 不可达（强失败）
    has_entry = any(
        c.type == SpaceConnectionType.EXTERIOR_ENTRY and ENTRY_NODE_ID in (c.a, c.b)
        for c in graph.connections
    )
    if not has_entry:
        return sorted(occupied)

    reached = reachable_nodes(graph, start=ENTRY_NODE_ID)
    return sorted(occupied - reached)

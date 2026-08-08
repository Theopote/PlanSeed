"""RoomGraph 构建与查询 — solver 拓扑层。"""

from __future__ import annotations

from collections import defaultdict, deque

from packages.schema.program import DesignProgram
from packages.schema.topology import RoomEdge, RoomEdgeKind, RoomGraph


def build_graph_from_program(program: DesignProgram) -> RoomGraph:
    """从 DesignProgram 约束与房间分类构建 RoomGraph。"""
    if program.room_graph is not None:
        return program.room_graph

    from packages.schema.project import ProjectSpec
    from solver.program.normalize import build_room_graph

    pseudo = ProjectSpec(
        site=program.site,
        floors=program.floors,
        rooms=program.rooms,
        constraints=program.constraints,
    )
    return build_room_graph(pseudo)


def edges_of_kind(graph: RoomGraph, kind: RoomEdgeKind) -> list[RoomEdge]:
    return [e for e in graph.edges if e.kind == kind]


def edges_for_room(graph: RoomGraph, room_id: str) -> list[RoomEdge]:
    """与 room_id 相关的全部边（不依赖 name）。"""
    return [
        e
        for e in graph.edges
        if e.source_id == room_id or e.target_id == room_id
    ]


def has_edge(
    graph: RoomGraph,
    a: str,
    b: str,
    *,
    kind: RoomEdgeKind | None = None,
) -> bool:
    for e in graph.edges:
        if kind is not None and e.kind != kind:
            continue
        if {e.source_id, e.target_id} == {a, b}:
            return True
    return False


def degree(graph: RoomGraph, room_id: str, *, kind: RoomEdgeKind | None = None) -> int:
    return len(
        {
            e.source_id if e.target_id == room_id else e.target_id
            for e in edges_for_room(graph, room_id)
            if kind is None or e.kind == kind
        }
    )


def neighbors(
    graph: RoomGraph, room_id: str, kind: RoomEdgeKind | None = None
) -> list[str]:
    result: list[str] = []
    for e in graph.edges:
        if kind is not None and e.kind != kind:
            continue
        if e.source_id == room_id:
            result.append(e.target_id)
        elif e.target_id == room_id:
            result.append(e.source_id)
    return result


def connected_components(
    graph: RoomGraph,
    *,
    kinds: set[RoomEdgeKind] | None = None,
) -> list[list[str]]:
    """
    无向连通分量（仅 room_id 节点）。

    kinds 为空则使用全部边类型。
    """
    adj: dict[str, set[str]] = defaultdict(set)
    nodes = set(graph.room_ids)
    for e in graph.edges:
        if kinds is not None and e.kind not in kinds:
            continue
        if e.source_id in nodes and e.target_id in nodes:
            adj[e.source_id].add(e.target_id)
            adj[e.target_id].add(e.source_id)

    visited: set[str] = set()
    components: list[list[str]] = []
    for rid in sorted(nodes):
        if rid in visited:
            continue
        comp: list[str] = []
        q: deque[str] = deque([rid])
        visited.add(rid)
        while q:
            cur = q.popleft()
            comp.append(cur)
            for nb in sorted(adj.get(cur, ())):
                if nb not in visited:
                    visited.add(nb)
                    q.append(nb)
        components.append(comp)
    return components

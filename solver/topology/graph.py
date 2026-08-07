"""RoomGraph 构建与查询 — solver 拓扑层。"""

from __future__ import annotations

from packages.schema.program import DesignProgram
from packages.schema.topology import RoomEdge, RoomEdgeKind, RoomGraph


def build_graph_from_program(program: DesignProgram) -> RoomGraph:
    """从 DesignProgram 约束与房间分类构建 RoomGraph。"""
    if program.room_graph is not None:
        return program.room_graph

    from packages.schema.project import ProjectSpec
    from solver.program.normalize import build_room_graph

    # 复用 Phase 0 逻辑：从 rooms + constraints 构建
    pseudo = ProjectSpec(
        site=program.site,
        floors=program.floors,
        rooms=program.rooms,
        constraints=program.constraints,
    )
    return build_room_graph(pseudo)


def edges_of_kind(graph: RoomGraph, kind: RoomEdgeKind) -> list[RoomEdge]:
    return [e for e in graph.edges if e.kind == kind]


def neighbors(graph: RoomGraph, room_id: str, kind: RoomEdgeKind | None = None) -> list[str]:
    result: list[str] = []
    for e in graph.edges:
        if kind is not None and e.kind != kind:
            continue
        if e.source_id == room_id:
            result.append(e.target_id)
        elif e.target_id == room_id:
            result.append(e.source_id)
    return result

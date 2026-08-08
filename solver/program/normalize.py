"""ProjectSpec → DesignProgram 规范化。"""

from __future__ import annotations

from packages.schema.constraints import (
    AdjacencyConstraint,
    AreaConstraint,
    ConstraintKind,
    ConstraintSource,
    OrientationConstraint,
    WidthConstraint,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.project import ProjectSpec
from packages.schema.room import RoomCategory
from packages.schema.topology import RoomEdge, RoomEdgeKind, RoomGraph
from solver.program.floor_assignment import ensure_floor_assignment


def normalize(spec: ProjectSpec, config: SolverConfig | None = None) -> DesignProgram:
    """
    将 ProjectSpec 规范化为 DesignProgram。

    - FloorAssignmentSolver：显式约束 → 住宅规则 → floor.room_ids
    - 推导 buildable envelope
    - 从 RoomSpec 字段生成 implicit constraints（若未显式提供）
    - 构建初始 RoomGraph
    """
    assignment = ensure_floor_assignment(spec.rooms, spec.floors, spec.constraints)
    program = DesignProgram.from_project(spec, config)
    program.floor_assignment = assignment
    program.constraints = _merge_implicit_constraints(spec, program.constraints)
    program.room_graph = build_room_graph(spec)
    return program


def _merge_implicit_constraints(spec: ProjectSpec, existing: list) -> list:
    by_kind_room: set[tuple] = {
        (c.kind, getattr(c, "room_id", None), getattr(c, "room_a_id", None))
        for c in existing
    }
    merged = list(existing)

    for room in spec.rooms:
        if room.min_area is not None:
            key = (ConstraintKind.AREA, room.id, None)
            if key not in by_kind_room:
                merged.append(
                    AreaConstraint(
                        id=f"area-min-{room.id}",
                        room_id=room.id,
                        min_area=room.min_area,
                        hard=True,
                        source=ConstraintSource.NORMALIZER,
                        source_key=f"rooms.{room.id}.min_area",
                    )
                )
        if room.min_width is not None:
            key = (ConstraintKind.WIDTH, room.id, None)
            if key not in by_kind_room:
                merged.append(
                    WidthConstraint(
                        id=f"width-min-{room.id}",
                        room_id=room.id,
                        min_width=room.min_width,
                        hard=True,
                        source=ConstraintSource.NORMALIZER,
                        source_key=f"rooms.{room.id}.min_width",
                    )
                )
        if room.preferred_orientation is not None:
            key = (ConstraintKind.ORIENTATION, room.id, None)
            if key not in by_kind_room:
                merged.append(
                    OrientationConstraint(
                        id=f"orient-{room.id}",
                        room_id=room.id,
                        preferred_orientation=room.preferred_orientation.value,
                        hard=False,
                        weight=0.8,
                        source=ConstraintSource.NORMALIZER,
                        source_key=f"rooms.{room.id}.preferred_orientation",
                    )
                )

    if spec.preferences.prefer_open_kitchen_dining:
        kitchen = _find_room(spec, tags=["kitchen"]) or _find_room(spec, names=["餐厅", "厨房"])
        dining = _find_room(spec, tags=["dining"]) or _find_room(spec, names=["餐厅"])
        if kitchen and dining and kitchen.id != dining.id:
            merged.append(
                AdjacencyConstraint(
                    id="pref-kitchen-dining",
                    room_a_id=kitchen.id,
                    room_b_id=dining.id,
                    hard=False,
                    weight=1.0,
                    description="厨房与餐厅邻接偏好",
                    source=ConstraintSource.NORMALIZER,
                    source_key="preferences.prefer_open_kitchen_dining",
                )
            )

    return merged


def _find_room(spec: ProjectSpec, tags: list[str] | None = None, names: list[str] | None = None):
    for room in spec.rooms:
        if tags and any(t in room.tags for t in tags):
            return room
        if names and any(n in room.name for n in names):
            return room
    return None


def build_room_graph(spec: ProjectSpec) -> RoomGraph:
    graph = RoomGraph(room_ids=[r.id for r in spec.rooms])

    for c in spec.constraints:
        if c.kind == ConstraintKind.ADJACENCY:
            graph.add_edge(
                RoomEdge(
                    source_id=c.room_a_id,
                    target_id=c.room_b_id,
                    kind=RoomEdgeKind.ADJACENT,
                    weight=c.weight,
                )
            )
        elif c.kind == ConstraintKind.SEPARATION:
            graph.add_edge(
                RoomEdge(
                    source_id=c.room_a_id,
                    target_id=c.room_b_id,
                    kind=RoomEdgeKind.AVOID,
                    weight=c.weight,
                )
            )

    wet_ids = [r.id for r in spec.rooms if r.category == RoomCategory.WET]
    for i, a in enumerate(wet_ids):
        for b in wet_ids[i + 1 :]:
            graph.add_edge(
                RoomEdge(source_id=a, target_id=b, kind=RoomEdgeKind.NEAR, weight=0.5)
            )

    return graph

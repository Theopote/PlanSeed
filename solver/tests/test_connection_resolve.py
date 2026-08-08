"""ConnectionResolver — 局部共边修补（不全局重排）。"""

from __future__ import annotations

from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.topology import (
    AccessGraph,
    SpaceConnection,
    SpaceConnectionType,
)
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.topology.connection_resolve import (
    resolve_required_connections,
)
from solver.topology.doors import shared_boundary_between


def _door_program() -> DesignProgram:
    site = SiteSpec(width=10, depth=10)
    rooms = [
        RoomSpec(
            id="hall", name="过厅", category=RoomCategory.CIRCULATION, target_area=8
        ),
        RoomSpec(
            id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12
        ),
    ]
    floors = [FloorSpec(id="F1", label="一层", room_ids=["hall", "bed"])]
    for r in rooms:
        r.floor_id = "F1"
    graph = AccessGraph()
    graph.add_connection(
        SpaceConnection(
            id="hall-bed",
            a="hall",
            b="bed",
            type=SpaceConnectionType.DOOR,
            required=True,
        )
    )
    return DesignProgram(
        project_id="conn-resolve",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        access_graph=graph,
        solver_config=SolverConfig(snap_module=0.3),
    )


class TestConnectionResolve:
    def test_closes_small_gap_between_required_pair(self):
        program = _door_program()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=4, depth=4),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        # 与 hall 左右对齐、缝隙 0.9m（≤ max_nudge）
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=4.9, y=0, width=4, depth=4),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        assert shared_boundary_between(hall, bed) is None
        n = resolve_required_connections(program, candidate)
        assert n == 1
        assert shared_boundary_between(hall, bed) is not None
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )
        assert len(candidate.door_openings) == 1

    def test_far_apart_not_repaired(self):
        program = _door_program()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=3, depth=3),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=6, y=6, width=3, depth=3),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        before = [p.rect.model_dump() for p in candidate.floors[0].placements]
        assert resolve_required_connections(program, candidate) == 0
        assert [p.rect.model_dump() for p in candidate.floors[0].placements] == before
        validation = DefaultConstraintChecker().check(program, candidate)
        assert any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )

    def test_lengthens_short_shared_edge(self):
        program = _door_program()
        # 竖向贴邻但 Y 重叠仅 0.5m < 0.9
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=4, depth=3),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=4, y=2.5, width=4, depth=3),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        assert shared_boundary_between(hall, bed, min_length=0.9) is None
        n = resolve_required_connections(program, candidate, min_wall=0.9)
        assert n == 1
        assert shared_boundary_between(hall, bed, min_length=0.9) is not None

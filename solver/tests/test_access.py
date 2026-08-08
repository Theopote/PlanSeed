"""Phase 2.3：RealizedAccessGraph — 共墙 ≠ 通行。"""

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
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import (
    AccessGraph,
    SpaceConnection,
    SpaceConnectionType,
)
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.generators.guillotine import GuillotineGenerator
from solver.program.floor_assignment import ensure_floor_assignment
from solver.tests.test_guillotine import benchmark_program
from solver.topology.access import (
    ENTRY_NODE_ID,
    build_realized_access_graph,
    unreachable_occupied_rooms,
)
from solver.topology.derive_access import ensure_access_graph
from solver.topology.doors import place_door_openings


def _program_two_rooms() -> DesignProgram:
    site = SiteSpec(width=10, depth=10, entrance_edge=CardinalEdge.SOUTH)
    rooms = [
        RoomSpec(
            id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20
        ),
        RoomSpec(
            id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12
        ),
    ]
    floors = [FloorSpec(id="F1", label="一层", room_ids=["living", "bed"])]
    for r in rooms:
        r.floor_id = "F1"
    return DesignProgram(
        project_id="access-test",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(),
    )


def _placement(
    room_id: str, *, x: float, y: float, w: float, d: float, cat: str
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id="F1",
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=room_id,
        category=cat,
    )


class TestRealizedAccessSemantics:
    def test_shared_wall_only_not_reachable(self):
        """共墙但无 Intent、且跳过 spanning OPEN → bed 不可达。"""
        program = _program_two_rooms()
        program.access_graph = AccessGraph()
        living = _placement("living", x=0, y=5, w=6, d=5, cat="public")
        bed = _placement("bed", x=0, y=0, w=6, d=5, cat="private")
        candidate = LayoutCandidate(
            id="wall-only",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, bed])],
        )
        # 仅 entry 边；不调用 place_door_openings（避免 spanning tree 开洞）
        missing = unreachable_occupied_rooms(program, candidate)
        assert "bed" in missing

    def test_shared_wall_plus_door_reachable(self):
        """共墙 + DOOR intent + DoorOpening → 可达。"""
        program = _program_two_rooms()
        graph = AccessGraph()
        graph.add_connection(
            SpaceConnection(
                id="living-bed",
                a="living",
                b="bed",
                type=SpaceConnectionType.DOOR,
                required=True,
            )
        )
        program.access_graph = graph
        living = _placement("living", x=0, y=5, w=6, d=5, cat="public")
        bed = _placement("bed", x=0, y=0, w=6, d=5, cat="private")
        candidate = LayoutCandidate(
            id="with-door",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, bed])],
        )
        place_door_openings(program, candidate)
        assert len(candidate.door_openings) == 1
        assert unreachable_occupied_rooms(program, candidate) == []
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "access.unreachable_room"
            for v in validation.hard_violations
        )

    def test_soft_door_realized_when_feasible(self):
        program = _program_two_rooms()
        graph = AccessGraph()
        graph.add_connection(
            SpaceConnection(
                id="living-bed-soft",
                a="living",
                b="bed",
                type=SpaceConnectionType.DOOR,
                required=False,
            )
        )
        program.access_graph = graph
        living = _placement("living", x=0, y=5, w=6, d=5, cat="public")
        bed = _placement("bed", x=0, y=0, w=6, d=5, cat="private")
        candidate = LayoutCandidate(
            id="soft",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, bed])],
        )
        place_door_openings(program, candidate)
        assert len(candidate.door_openings) == 1
        assert unreachable_occupied_rooms(program, candidate) == []

    def test_required_door_blocked_invalid(self):
        program = _program_two_rooms()
        graph = AccessGraph()
        graph.add_connection(
            SpaceConnection(
                id="living-bed",
                a="living",
                b="bed",
                type=SpaceConnectionType.DOOR,
                required=True,
            )
        )
        program.access_graph = graph
        living = _placement("living", x=0, y=7, w=4, d=3, cat="public")
        bed = _placement("bed", x=6, y=0, w=3, d=3, cat="private")
        candidate = LayoutCandidate(
            id="blocked",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, bed])],
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid is False
        assert any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )

    def test_entry_edge_present(self):
        program = _program_two_rooms()
        living = _placement("living", x=0, y=5, w=6, d=5, cat="public")
        candidate = LayoutCandidate(
            id="entry",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living])],
        )
        graph = build_realized_access_graph(program, candidate)
        assert any(
            ENTRY_NODE_ID in (c.a, c.b) and "living" in (c.a, c.b)
            for c in graph.connections
        )

    def test_benchmark_candidate_has_no_unreachable(self):
        program = benchmark_program()
        ensure_floor_assignment(program.rooms, program.floors, program.constraints)
        ensure_access_graph(program)
        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        unreachable = [
            v
            for v in validation.hard_violations
            if v.constraint_id == "access.unreachable_room"
        ]
        assert unreachable == [], unreachable

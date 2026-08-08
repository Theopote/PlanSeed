"""access.unreachable_room — occupied space 必须从 Entry 可达。"""

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
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.generators.guillotine import GuillotineGenerator
from solver.program.floor_assignment import ensure_floor_assignment
from solver.tests.test_guillotine import benchmark_program
from solver.topology.access import (
    ENTRY_NODE_ID,
    build_realized_access_graph,
    unreachable_occupied_rooms,
)


def _program_two_rooms() -> DesignProgram:
    site = SiteSpec(width=10, depth=10, entrance_edge=CardinalEdge.SOUTH)
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12),
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


def _placement(room_id: str, *, x: float, y: float, w: float, d: float, cat: str) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id="F1",
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=room_id,
        category=cat,
    )


class TestAccessReachability:
    def test_connected_from_entry_is_reachable(self):
        """南侧外墙客厅 + 共边卧室 → 均可从 entry 到达。"""
        program = _program_two_rooms()
        # buildable 10×10；y 增大向南 → 南墙 y+d ≈ 10
        living = _placement("living", x=0, y=5, w=6, d=5, cat="public")
        bed = _placement("bed", x=0, y=0, w=6, d=5, cat="private")
        candidate = LayoutCandidate(
            id="ok",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, bed])],
        )
        assert unreachable_occupied_rooms(program, candidate) == []
        graph = build_realized_access_graph(program, candidate)
        assert any(
            ENTRY_NODE_ID in (c.a, c.b) and "living" in (c.a, c.b)
            for c in graph.connections
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "access.unreachable_room" for v in validation.hard_violations
        )

    def test_island_room_unreachable(self):
        """卧室与入口侧客厅无共边 → bed 不可达。"""
        program = _program_two_rooms()
        living = _placement("living", x=0, y=7, w=4, d=3, cat="public")
        # 孤立块：不贴南墙、不与 living 共边
        bed = _placement("bed", x=6, y=0, w=3, d=3, cat="private")
        candidate = LayoutCandidate(
            id="bad",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, bed])],
        )
        missing = unreachable_occupied_rooms(program, candidate)
        assert "bed" in missing
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid is False
        hit = [
            v for v in validation.hard_violations if v.constraint_id == "access.unreachable_room"
        ]
        assert hit
        assert "bed" in hit[0].room_ids

    def test_benchmark_candidate_has_no_unreachable(self):
        program = benchmark_program()
        ensure_floor_assignment(program.rooms, program.floors, program.constraints)
        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        unreachable = [
            v for v in validation.hard_violations if v.constraint_id == "access.unreachable_room"
        ]
        # 连通 guillotine 布局不应出现入口孤岛；若有则暴露真实缺陷
        assert unreachable == [], unreachable

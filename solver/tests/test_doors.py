"""Phase 2A：共边校验 + DoorOpening 标注（不回改房间几何）。"""

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
from solver.topology.doors import place_door_openings, shared_boundary_between


def _program_with_door_conn(*, required: bool = True) -> DesignProgram:
    site = SiteSpec(width=10, depth=10)
    rooms = [
        RoomSpec(id="hall", name="过厅", category=RoomCategory.CIRCULATION, target_area=8),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12),
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
            required=required,
        )
    )
    return DesignProgram(
        project_id="door-2a",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        access_graph=graph,
        solver_config=SolverConfig(),
    )


class TestDoorPhase2A:
    def test_shared_edge_places_opening_without_moving_rooms(self):
        program = _program_with_door_conn()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=4, depth=4),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=4, y=0, width=4, depth=4),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        rects_before = [p.rect.model_dump() for p in candidate.floors[0].placements]
        assert shared_boundary_between(hall, bed) is not None

        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )
        assert len(candidate.door_openings) == 1
        op = candidate.door_openings[0]
        assert {op.room_a_id, op.room_b_id} == {"hall", "bed"}
        # 几何未动
        assert [p.rect.model_dump() for p in candidate.floors[0].placements] == rects_before

    def test_no_shared_edge_hard_invalid(self):
        program = _program_with_door_conn()
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
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid is False
        hit = [
            v
            for v in validation.hard_violations
            if v.constraint_id == "access.missing_shared_boundary"
        ]
        assert hit
        assert candidate.door_openings == []

    def test_place_door_openings_idempotent_geometry(self):
        program = _program_with_door_conn()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=1, width=5, depth=4),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=5, y=1, width=4, depth=4),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=1,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        dump = candidate.model_dump(exclude={"door_openings"})
        place_door_openings(program, candidate)
        assert len(candidate.door_openings) == 1
        assert candidate.model_dump(exclude={"door_openings"}) == dump

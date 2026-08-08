"""Phase 2A/2.2：共边校验 + DoorOpening polish（不回改房间几何）。"""

from __future__ import annotations

from packages.schema.layout import (
    DoorOpening,
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
from solver.constraints.checker import ConstraintEvaluationResult
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.topology.doors import (
    MIN_CLEAR_WIDTH,
    choose_swing_room,
    door_clear_width_violations,
    place_door_openings,
    shared_boundary_between,
)
from solver.visualize.svg import render_candidate_svg


def _program_with_door_conn(*, required: bool = True) -> DesignProgram:
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


class TestDoorPhase22Polish:
    def test_swing_into_private_not_hall(self):
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
        assert choose_swing_room(hall, bed).room_id == "bed"

        program = _program_with_door_conn()
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        place_door_openings(program, candidate)
        op = candidate.door_openings[0]
        assert op.swing_room_id == "bed"
        assert op.hinge_side in ("left", "right")
        assert op.hinge_x is not None and op.hinge_y is not None
        assert op.clear_width >= MIN_CLEAR_WIDTH - 1e-9
        assert op.axis == "y"

    def test_clear_width_soft_violation(self):
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[],
            door_openings=[
                DoorOpening(
                    id="narrow",
                    room_a_id="hall",
                    room_b_id="bed",
                    floor_id="F1",
                    x=4,
                    y=2,
                    width=0.6,
                    axis="y",
                    connection_type="door",
                    clear_width=0.6,
                    swing_room_id="bed",
                    hinge_side="left",
                    hinge_x=4,
                    hinge_y=1.7,
                )
            ],
        )
        viols = door_clear_width_violations(candidate, preferred_clear=0.8)
        assert len(viols) == 1
        assert viols[0].constraint_id == "door.physical_min_width"
        assert viols[0].hard is False
        soft_result = ConstraintEvaluationResult.from_violations(viols)
        assert soft_result.valid is True
        assert soft_result.soft_violations

    def test_svg_draws_door_leaf(self):
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
        place_door_openings(program, candidate)
        svg = render_candidate_svg(
            candidate,
            floor_width=10,
            floor_depth=10,
            site=program.site,
            access_graph=program.access_graph,
        )
        assert "doors=1" in svg
        assert "<path d=" in svg

"""ADR-010 STAIR/ATRIUM 预扣除 solver 回归。"""

from __future__ import annotations

import pytest
from packages.schema.core import CorePlacement
from packages.schema.layout import PlacementSource
from packages.schema.vertical_void import VerticalVoidSpec, VerticalVoidType
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.coverage import COVERAGE_TOLERANCE, floor_coverage_gap
from solver.vertical.prededuction import build_prededuction_plan


def _program_with_atrium(*, width: float = 3.0, depth: float = 3.0) -> object:
    program = benchmark_program()
    program.vertical_voids = [
        VerticalVoidSpec(
            id="atrium-1",
            void_type=VerticalVoidType.ATRIUM,
            floor_span=("F1", "F2"),
            width=width,
            depth=depth,
            preferred_placement=CorePlacement.CENTER,
            skylight_required=True,
        )
    ]
    return program


class TestPredeductionPlan:
    def test_atrium_void_on_both_floors(self) -> None:
        program = _program_with_atrium()
        plan = build_prededuction_plan(
            program,
            floor_width=program.buildable.width,
            floor_depth=program.buildable.depth,
            snap_module=0.3,
            rng=__import__("random").Random(0),
        )
        assert len(plan.void_placements) == 2
        assert {vp.floor_id for vp in plan.void_placements} == {"F1", "F2"}
        f1_rect = plan.void_placements[0].rect
        f2_rect = next(vp.rect for vp in plan.void_placements if vp.floor_id == "F2")
        assert f1_rect.x == pytest.approx(f2_rect.x)
        assert f1_rect.y == pytest.approx(f2_rect.y)

    def test_atrium_hole_only_on_span_floor(self) -> None:
        program = _program_with_atrium()
        plan = build_prededuction_plan(
            program,
            floor_width=program.buildable.width,
            floor_depth=program.buildable.depth,
            snap_module=0.3,
            rng=__import__("random").Random(1),
        )
        stair = plan.holes_by_floor["F1"]
        assert len(stair) >= 2  # stair + atrium on F1


class TestGuillotineAtriumPrededuction:
    def test_generated_void_placements_on_candidate(self) -> None:
        program = _program_with_atrium()
        candidate = GuillotineGenerator().generate(program, seed=0)
        assert len(candidate.vertical_void_placements) == 2
        void_rooms = [
            p
            for fl in candidate.floors
            for p in fl.placements
            if p.room_id.startswith("void-")
        ]
        assert len(void_rooms) == 2
        assert all(p.source == PlacementSource.GENERATED for p in void_rooms)

    def test_atrium_floors_still_fully_covered(self) -> None:
        program = _program_with_atrium()
        footprint = program.buildable.width * program.buildable.depth
        candidate = GuillotineGenerator().generate(program, seed=1)
        for floor in candidate.floors:
            gap = floor_coverage_gap(footprint, floor.placements)
            assert abs(gap) <= COVERAGE_TOLERANCE, f"{floor.floor_id} gap={gap}"

    def test_valid_candidate_with_atrium(self) -> None:
        program = _program_with_atrium()
        candidate = GuillotineGenerator().generate(program, seed=1)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid, validation.hard_violations

    def test_benchmark_without_voids_unchanged(self) -> None:
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        assert candidate.vertical_void_placements == []
        stairs = [
            p
            for fl in candidate.floors
            for p in fl.placements
            if p.room_id.startswith("stair-")
        ]
        assert len(stairs) == 2

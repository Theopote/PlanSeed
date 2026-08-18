"""房间长宽比硬约束回归。"""

from __future__ import annotations

import pytest
from packages.schema.layout import PlacementRect, RoomPlacement
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.evaluation.geometry import (
    is_aspect_ratio_exempt_placement,
    room_aspect_ratio_violations,
)
from solver.evaluation.weights import DEFAULT_WEIGHTS
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.pipeline import run_pipeline
from solver.tests.test_vertical_void_prededuction import _program_with_atrium


def _atrium_benchmark_program():
    return _program_with_atrium()


def _functional_placements(candidate) -> list[RoomPlacement]:
    out: list[RoomPlacement] = []
    for floor in candidate.floors:
        for p in floor.placements:
            if is_aspect_ratio_exempt_placement(p):
                continue
            out.append(p)
    return out


class TestRoomAspectRatioViolations:
    def test_slender_functional_room_rejected(self) -> None:
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        slender = RoomPlacement(
            room_id="r10",
            floor_id="F2",
            rect=PlacementRect(x=1.8, y=4.5, width=9.2, depth=0.6),
            name="书房",
            category="other",
        )
        for floor in candidate.floors:
            floor.placements = [p for p in floor.placements if p.room_id != "r10"]
            if floor.floor_id == "F2":
                floor.placements.append(slender)

        violations = room_aspect_ratio_violations(candidate)
        assert any(v.constraint_id == "geometry.room_aspect_ratio" for v in violations)
        assert slender.aspect_ratio > DEFAULT_WEIGHTS.aspect_ratio_threshold

        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(
            v.constraint_id == "geometry.room_aspect_ratio"
            for v in validation.hard_violations
        )

    def test_circulation_and_void_exempt(self) -> None:
        stair = RoomPlacement(
            room_id="stair-F1",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=1.8, depth=12.0),
            name="楼梯",
            category="circulation",
        )
        void = RoomPlacement(
            room_id="void-atrium-1",
            floor_id="F1",
            rect=PlacementRect(x=4, y=4, width=3, depth=0.5),
            name="天井",
            category="circulation",
        )
        corridor = RoomPlacement(
            room_id="corr-1",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=10, depth=0.8),
            name="走廊",
            category="circulation",
        )
        assert is_aspect_ratio_exempt_placement(stair)
        assert is_aspect_ratio_exempt_placement(void)
        assert is_aspect_ratio_exempt_placement(corridor)

    def test_seed44_atrium_slender_strip_eliminated(self) -> None:
        """用户复现：seed=44 不再产出 9.2×0.6 书房条带。"""
        program = _atrium_benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=44)
        r10 = next(
            p
            for fl in candidate.floors
            for p in fl.placements
            if p.room_id == "r10"
        )
        assert r10.rect.width < 8.0
        assert r10.aspect_ratio <= DEFAULT_WEIGHTS.aspect_ratio_threshold + 1e-6

    def test_seed44_atrium_pipeline_top_study_not_slender(self) -> None:
        program = _atrium_benchmark_program()
        program.solver_config.base_seed = 44
        program.solver_config.candidate_count = 64
        program.solver_config.return_top_k = 5
        result = run_pipeline(program)
        assert len(result.top_candidates) >= 5
        limit = DEFAULT_WEIGHTS.aspect_ratio_threshold
        for candidate in result.top_candidates:
            assert candidate.validation is not None and candidate.validation.valid
            r10 = next(
                p
                for fl in candidate.floors
                for p in fl.placements
                if p.room_id == "r10"
            )
            assert r10.aspect_ratio <= limit + 1e-6, (
                f"r10 {r10.rect.width:.2f}×{r10.rect.depth:.2f} "
                f"ratio={r10.aspect_ratio:.2f}"
            )


def _assert_valid_candidates_respect_aspect_ratio(seed: int) -> None:
    program = _atrium_benchmark_program()
    program.solver_config.base_seed = seed
    program.solver_config.candidate_count = 64
    program.solver_config.return_top_k = 5
    result = run_pipeline(program)
    limit = DEFAULT_WEIGHTS.aspect_ratio_threshold
    valid_candidates = [
        c for c in result.all_candidates if c.validation and c.validation.valid
    ]
    for candidate in valid_candidates:
        for p in _functional_placements(candidate):
            assert p.aspect_ratio <= limit + 1e-6, (
                f"seed={seed} {candidate.id} {p.room_id} "
                f"ratio={p.aspect_ratio:.2f}"
            )
    for candidate in result.top_candidates:
        for p in _functional_placements(candidate):
            assert p.aspect_ratio <= limit + 1e-6


class TestPipelineAspectRatioWithAtrium:
    @pytest.mark.parametrize("seed", range(20))
    def test_valid_candidates_respect_aspect_ratio(self, seed: int) -> None:
        _assert_valid_candidates_respect_aspect_ratio(seed)


class TestPipelineAspectRatioWithAtriumSlow:
    @pytest.mark.slow
    @pytest.mark.parametrize("seed", range(101))
    def test_valid_candidates_respect_aspect_ratio_full_sample(self, seed: int) -> None:
        _assert_valid_candidates_respect_aspect_ratio(seed)

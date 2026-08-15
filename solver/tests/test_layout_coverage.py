"""楼层平面覆盖率回归 — 可建面积须被 placements 完全铺满。"""

from __future__ import annotations

import pytest
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.coverage import COVERAGE_TOLERANCE, floor_coverage_gap
from solver.pipeline import run_pipeline


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 7, 42])
def test_guillotine_benchmark_floor_fully_covered(seed: int) -> None:
    program = benchmark_program()
    footprint = program.buildable.width * program.buildable.depth
    candidate = GuillotineGenerator().generate(program, seed=seed)
    for floor in candidate.floors:
        gap = floor_coverage_gap(footprint, floor.placements)
        assert abs(gap) <= COVERAGE_TOLERANCE, (
            f"seed={seed} floor={floor.floor_id} gap={gap}"
        )


def test_pipeline_top_candidates_fully_cover_footprint() -> None:
    program = benchmark_program()
    program.solver_config.candidate_count = 64
    program.solver_config.return_top_k = 5
    footprint = program.buildable.width * program.buildable.depth

    result = run_pipeline(program)
    assert result.top_candidates, "expected Top-K candidates"
    assert result.valid < result.generated, "area/coverage gate should reject some candidates"

    for candidate in result.top_candidates:
        for floor in candidate.floors:
            gap = floor_coverage_gap(footprint, floor.placements)
            assert abs(gap) <= COVERAGE_TOLERANCE, (
                f"{candidate.id} floor={floor.floor_id} gap={gap}"
            )
        assert candidate.validation is not None and candidate.validation.valid

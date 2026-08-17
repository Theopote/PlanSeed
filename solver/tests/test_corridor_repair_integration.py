"""ADR-011 — 走廊邻接修补集成回归。"""

from __future__ import annotations

from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline
from solver.tests.quality_baselines import MEASURED_BASELINE


class TestCorridorRepairIntegration:
    def test_valid_ratio_not_regressed_by_corridor_repair(self) -> None:
        """checker 门控的走廊修补不得拉低 benchmark valid_ratio。"""
        program = benchmark_program()
        program.solver_config.candidate_count = 64
        result = run_pipeline(program)
        ratio = result.valid / result.generated
        soft_floor = max(0.3, MEASURED_BASELINE["valid_ratio"] - 0.05)
        assert ratio >= soft_floor, (
            f"valid_ratio={ratio:.3f} < soft_floor {soft_floor:.3f} "
            f"(valid={result.valid}/{result.generated}; "
            f"measured={MEASURED_BASELINE['valid_ratio']})"
        )

"""ADR-011 — 走廊邻接修补集成回归。"""

from __future__ import annotations

from unittest.mock import patch

from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline
from solver.tests.quality_baselines import MEASURED_BASELINE


def _count_corridor_repair_strips(candidate) -> int:
    """识别 ADR-011 借边切出的 0.9m 走廊条（非残余碎片）。"""
    total = 0
    for floor in candidate.floors:
        for placement in floor.placements:
            if not placement.room_id.startswith("circ-"):
                continue
            short = min(placement.rect.width, placement.rect.depth)
            long = max(placement.rect.width, placement.rect.depth)
            if abs(short - 0.9) < 0.05 and long + 1e-9 >= 0.9 * 1.5:
                total += 1
    return total


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

    def test_top_candidates_avoid_private_through(self) -> None:
        """benchmark Top-5 不应再普遍出现穿其他卧室到达主卧。"""
        from solver.evaluation.privacy import compute_privacy_metrics

        program = benchmark_program()
        program.solver_config.candidate_count = 64
        program.solver_config.return_top_k = 5
        result = run_pipeline(program)
        assert len(result.top_candidates) >= 5

        through_hits = 0
        for top in result.top_candidates:
            metrics = compute_privacy_metrics(program, top)
            if int(metrics.get("private_through_count", 0)) > 0:
                through_hits += 1

        rate = through_hits / len(result.top_candidates)
        assert rate <= 0.5, (
            f"private_through top rate {rate:.0%} ({through_hits}/"
            f"{len(result.top_candidates)}) expected <= 50%"
        )

    def test_valid_candidates_gain_corridor_strips(self) -> None:
        """在 valid 候选上，修补应实际生效（非空转）。"""
        import solver.generators.guillotine as gmod

        program = benchmark_program()
        program.solver_config.candidate_count = 64

        with patch.object(
            gmod,
            "apply_corridor_access_repair_if_safe",
            side_effect=lambda _p, cand, *_a, **_k: cand,
        ):
            baseline = run_pipeline(program)

        repaired = run_pipeline(program)
        improved = 0
        for base, cand in zip(baseline.all_candidates, repaired.all_candidates):
            if not cand.validation or not cand.validation.valid:
                continue
            if _count_corridor_repair_strips(cand) > _count_corridor_repair_strips(base):
                improved += 1

        assert improved >= 5, (
            f"expected >=5 valid candidates with new corridor strips, got {improved}"
        )


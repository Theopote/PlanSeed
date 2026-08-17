"""ADR-011 — 走廊邻接修补集成回归。"""

from __future__ import annotations

from solver.evaluation.privacy import compute_privacy_metrics
from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline


class TestCorridorRepairIntegration:
    def test_top_candidates_private_through_rate_below_half(self) -> None:
        """benchmark Top-5 中 private_through_count>0 的比例应明显低于修补前基线 100%。"""
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

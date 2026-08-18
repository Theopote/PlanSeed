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

    def test_unavoidable_private_through_documented_on_benchmark(self) -> None:
        """部分 valid 布局结构上无法消除穿卧室；应能区分 unavoidable 计数。"""
        from solver.evaluation.privacy import compute_privacy_metrics

        program = benchmark_program()
        program.solver_config.candidate_count = 64
        result = run_pipeline(program)
        unavoidable_hits = 0
        for cand in result.all_candidates:
            if not cand.validation or not cand.validation.valid:
                continue
            metrics = compute_privacy_metrics(program, cand)
            if int(metrics.get("unavoidable_private_through_count", 0)) > 0:
                unavoidable_hits += 1
        assert unavoidable_hits >= 1
        assert unavoidable_hits <= result.valid

    def test_valid_candidates_gain_circulation_passages(self) -> None:
        """valid 候选应通过走廊 PASSAGE 接入 RealizedAccessGraph。"""
        from solver.topology.access import build_realized_connections

        program = benchmark_program()
        program.solver_config.candidate_count = 64
        result = run_pipeline(program)

        with_passage = 0
        for cand in result.all_candidates:
            if not cand.validation or not cand.validation.valid:
                continue
            realized = build_realized_connections(program, cand)
            if any(rc.source == "circulation_passage" for rc in realized):
                with_passage += 1

        assert with_passage >= 5, (
            f"expected >=5 valid candidates with circulation_passage, got {with_passage}"
        )


"""Phase 8.2 — multi-generator pool + Pareto。"""

from __future__ import annotations

from solver.fixtures.benchmark import benchmark_program
from solver.generators import GuillotineGenerator, MaxRectGenerator
from solver.pipeline import run_pipeline


def test_pipeline_pareto_tags_top_candidates():
    program = benchmark_program()
    program.solver_config.candidate_count = 8
    program.solver_config.return_top_k = 3
    program.solver_config.rank_mode = "pareto"
    result = run_pipeline(program)
    assert result.generated == 8
    assert len(result.top_candidates) == 3
    roles = [c.metrics.get("selection_role") for c in result.top_candidates]
    assert "pareto" in roles
    assert all(r in ("pareto", "diverse") for r in roles)


def test_pipeline_multi_generator_pool():
    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 3
    program.solver_config.rank_mode = "pareto"
    result = run_pipeline(
        program,
        generators=[GuillotineGenerator(), MaxRectGenerator()],
    )
    assert result.generated == 8  # 4 per strategy
    ids = {c.id for c in result.all_candidates}
    assert len(ids) == 8
    assert len(result.top_candidates) == 3
    # provenance 应覆盖两种 generator（池内至少出现过）
    versions = {
        c.provenance.generator_version
        for c in result.all_candidates
        if c.provenance is not None
    }
    assert "maxrect-v1" in versions

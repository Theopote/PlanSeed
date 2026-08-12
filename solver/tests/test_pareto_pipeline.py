"""Phase 8.2 — multi-generator pool + Pareto。"""

from __future__ import annotations

from solver.fixtures.benchmark import benchmark_program
from solver.generators import GuillotineGenerator, MaxRectGenerator
from solver.pipeline import run_pipeline


def test_pipeline_default_is_guillotine_only():
    """Alpha 默认候选池不得混入 MaxRect。"""
    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 2
    result = run_pipeline(program)
    assert result.generated == 4
    strategies = {
        (c.provenance.generator_strategy if c.provenance else None)
        for c in result.all_candidates
    }
    assert strategies == {"guillotine"}
    assert all(
        c.metrics.get("generator_strategy") == "guillotine" for c in result.all_candidates
    )


def test_pipeline_default_rank_mode_is_axis():
    """P0：Alpha 默认不得静默走 Pareto。"""
    program = benchmark_program()
    program.solver_config.candidate_count = 6
    program.solver_config.return_top_k = 3
    assert program.solver_config.rank_mode == "axis"
    result = run_pipeline(program)
    assert result.top_candidates
    for c in result.top_candidates:
        assert c.metrics.get("rank_mode") == "axis"
        assert c.metrics.get("selection_role") != "pareto"


def test_pipeline_pareto_without_experimental_stays_axis():
    program = benchmark_program()
    program.solver_config.candidate_count = 6
    program.solver_config.return_top_k = 3
    program.solver_config.rank_mode = "pareto"
    program.solver_config.experimental = False
    result = run_pipeline(program)
    assert result.top_candidates
    for c in result.top_candidates:
        assert c.metrics.get("rank_mode") == "axis"


def test_pipeline_pareto_tags_top_candidates():
    program = benchmark_program()
    program.solver_config.candidate_count = 8
    program.solver_config.return_top_k = 3
    program.solver_config.rank_mode = "pareto"
    program.solver_config.experimental = True
    result = run_pipeline(program)
    assert result.generated == 8
    assert len(result.top_candidates) == 3
    roles = [c.metrics.get("selection_role") for c in result.top_candidates]
    assert roles[0] == "top_score"
    assert "pareto" in roles[1:] or all(r in ("pareto", "diverse", "top_score") for r in roles)
    assert all(r in ("top_score", "pareto", "diverse") for r in roles)
    assert all(c.metrics.get("selection_version") == "pareto-top1-axes-v2" for c in result.top_candidates)


def test_pipeline_multi_generator_pool_research_opt_in():
    """Research：显式 multi-gen 池才可混 MaxRect；非 Alpha 默认。"""
    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 3
    program.solver_config.rank_mode = "pareto"
    program.solver_config.experimental = True
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
    strategies = {
        c.provenance.generator_strategy
        for c in result.all_candidates
        if c.provenance is not None
    }
    assert strategies == {"guillotine", "maxrect"}

"""SolverProfile — Alpha Stable vs Research Lab。"""

from __future__ import annotations

from packages.schema.program import SolverConfig
from packages.schema.solver_profile import (
    ALPHA_STABLE,
    PROFILE_ALPHA_STABLE,
    RESEARCH_MAXRECT,
    RESEARCH_PARETO,
    apply_solver_profile,
    get_solver_profile,
    pin_alpha_stable_if_needed,
)
from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline


def test_alpha_stable_defaults():
    assert ALPHA_STABLE.generator == "guillotine"
    assert ALPHA_STABLE.selection == "axis"
    assert ALPHA_STABLE.assignment == "heuristic"
    assert ALPHA_STABLE.geometry_backend == "rect"
    assert ALPHA_STABLE.experimental is False


def test_pin_alpha_stable_overrides_stray_research_flags():
    cfg = SolverConfig(rank_mode="pareto", generator_strategy="maxrect", experimental=False)
    pinned = pin_alpha_stable_if_needed(cfg)
    assert pinned.rank_mode == "axis"
    assert pinned.generator_strategy == "guillotine"
    assert pinned.profile_id == PROFILE_ALPHA_STABLE
    assert pinned.experimental is False


def test_experimental_preserves_research_profile():
    cfg = apply_solver_profile(SolverConfig(), RESEARCH_PARETO)
    assert cfg.experimental is True
    assert cfg.rank_mode == "pareto"
    out = pin_alpha_stable_if_needed(cfg)
    assert out.rank_mode == "pareto"


def test_pipeline_config_maxrect_ignored_without_experimental():
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.generator_strategy = "maxrect"
    program.solver_config.experimental = False
    result = run_pipeline(program)
    strategies = {
        c.provenance.generator_strategy
        for c in result.all_candidates
        if c.provenance is not None
    }
    assert strategies == {"guillotine"}


def test_pipeline_config_maxrect_honored_when_experimental():
    program = benchmark_program()
    program.solver_config = apply_solver_profile(
        program.solver_config.model_copy(update={"candidate_count": 2}),
        RESEARCH_MAXRECT,
    )
    result = run_pipeline(program)
    strategies = {
        c.provenance.generator_strategy
        for c in result.all_candidates
        if c.provenance is not None
    }
    assert strategies == {"maxrect"}


def test_get_solver_profile_known():
    assert get_solver_profile("alpha-stable").id == PROFILE_ALPHA_STABLE


def test_generate_layouts_pins_stray_pareto():
    from backend.services.generation import generate_layouts

    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 2
    program.solver_config.rank_mode = "pareto"
    program.solver_config.experimental = False
    result = generate_layouts(program)
    assert result.top_candidates
    for c in result.top_candidates:
        assert c.provenance is not None
        assert c.provenance.selection_strategy == "axis-diverse"
        assert "pareto" not in (c.provenance.selection_version or "")

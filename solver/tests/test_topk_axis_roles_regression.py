"""Alpha 默认 Top-K 角色分布回归（固定 fixture）。"""

from __future__ import annotations

from packages.schema.identity import SELECTION_VERSION
from solver.fixtures.topk_axis_roles import (
    BUILDABLE_DEPTH,
    BUILDABLE_WIDTH,
    EXPECTED_RANK_MODE,
    EXPECTED_SELECTION_VERSION,
    EXPECTED_TOP_ROLES,
    FIXTURE_ID,
    MIN_DIVERSITY_THRESHOLD,
    TOP_K,
    axis_topk_role_pool,
)
from solver.optimization.rank import DEFAULT_RANK_MODE, rank_candidates


def test_fixture_constants_match_alpha_identity():
    assert EXPECTED_SELECTION_VERSION == SELECTION_VERSION
    assert EXPECTED_RANK_MODE == DEFAULT_RANK_MODE == "axis"
    assert FIXTURE_ID == "topk-axis-roles-v1"
    assert len(EXPECTED_TOP_ROLES) == TOP_K


def test_default_axis_topk_role_sequence_locked():
    """默认 mode（不传 / axis）必须产出冻结角色序列。"""
    pool = axis_topk_role_pool()
    ranked = rank_candidates(
        pool,
        top_k=TOP_K,
        min_diversity_threshold=MIN_DIVERSITY_THRESHOLD,
        buildable_width=BUILDABLE_WIDTH,
        buildable_depth=BUILDABLE_DEPTH,
    )
    got = [
        (c.id, c.metrics.get("selection_role"), c.metrics.get("selection_label"))
        for c in ranked
    ]
    assert got == list(EXPECTED_TOP_ROLES)
    assert all(c.metrics.get("rank_mode") == "axis" for c in ranked)
    assert all(
        c.metrics.get("selection_version") == EXPECTED_SELECTION_VERSION for c in ranked
    )
    assert "c-invalid" not in {c.id for c in ranked}
    assert "c-near-top" not in {c.id for c in ranked}


def test_explicit_axis_matches_default_mode():
    pool = axis_topk_role_pool()
    kwargs = dict(
        top_k=TOP_K,
        min_diversity_threshold=MIN_DIVERSITY_THRESHOLD,
        buildable_width=BUILDABLE_WIDTH,
        buildable_depth=BUILDABLE_DEPTH,
    )
    defaulted = rank_candidates(pool, **kwargs)
    explicit = rank_candidates(axis_topk_role_pool(), mode="axis", **kwargs)
    assert [c.id for c in defaulted] == [c.id for c in explicit]
    assert [c.metrics.get("selection_role") for c in defaulted] == [
        c.metrics.get("selection_role") for c in explicit
    ]


def test_pareto_opt_in_diverges_from_axis_fixture():
    """防止再次把 Pareto 默认为主路径：同池 Pareto 不得等于 axis 冻结序列。"""
    pool = axis_topk_role_pool()
    axis = rank_candidates(
        pool,
        top_k=TOP_K,
        min_diversity_threshold=MIN_DIVERSITY_THRESHOLD,
        buildable_width=BUILDABLE_WIDTH,
        buildable_depth=BUILDABLE_DEPTH,
        mode="axis",
    )
    pareto = rank_candidates(
        axis_topk_role_pool(),
        top_k=TOP_K,
        min_diversity_threshold=MIN_DIVERSITY_THRESHOLD,
        buildable_width=BUILDABLE_WIDTH,
        buildable_depth=BUILDABLE_DEPTH,
        mode="pareto",
    )
    axis_ids = [c.id for c in axis]
    pareto_roles = [c.metrics.get("selection_role") for c in pareto]
    assert axis_ids == [row[0] for row in EXPECTED_TOP_ROLES]
    assert pareto_roles != [row[1] for row in EXPECTED_TOP_ROLES]
    assert all(r in ("pareto", "diverse") for r in pareto_roles)
    assert all(c.metrics.get("selection_version") == "pareto-crowding-v1" for c in pareto)

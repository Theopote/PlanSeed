"""Phase 8.2 — Pareto non-dominated selection（experimental）。"""

from __future__ import annotations

from packages.schema.layout import (
    CandidateValidation,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.scoring import DesignScore
from solver.optimization.pareto import (
    PARETO_OBJECTIVES,
    dominates,
    objective_vector,
    pareto_front,
    select_pareto_frontier,
)
from solver.optimization.rank import rank_candidates


def _cand(
    *,
    cid: str,
    seed: int,
    total: float,
    program: float | None = None,
    spatial: float,
    circ: float,
    priv: float,
    env: float,
    x: float = 0.0,
) -> LayoutCandidate:
    floors = [
        FloorLayout(
            floor_id="F1",
            placements=[
                RoomPlacement(
                    room_id="r1",
                    floor_id="F1",
                    rect=PlacementRect(x=x, y=0, width=4, depth=4),
                    source=PlacementSource.PROGRAM,
                    name="R",
                    category="public",
                )
            ],
        )
    ]
    prog = total if program is None else program
    ev = DesignScore(
        total_score=total,
        program_score=prog,
        spatial_score=spatial,
        circulation_score=circ,
        privacy_score=priv,
        environment_score=env,
        technical_score=50.0,
        robustness_score=50.0,
    )
    return LayoutCandidate(
        id=cid,
        seed=seed,
        floors=floors,
        score=total,
        evaluation=ev,
        validation=CandidateValidation(valid=True),
        metrics={},
    )


def test_pareto_objectives_reuse_seven_axis_language():
    keys = [k for k, _r, _l in PARETO_OBJECTIVES]
    roles = [r for _k, r, _l in PARETO_OBJECTIVES]
    labels = [lab for _k, _r, lab in PARETO_OBJECTIVES]
    assert keys == [
        "program_score",
        "spatial_score",
        "circulation_score",
        "privacy_score",
        "environment_score",
    ]
    assert "efficiency" not in roles
    assert "效率更好" not in labels
    assert roles == ["program", "spatial", "circulation", "privacy", "environment"]


def test_dominates_basic():
    a = _cand(cid="a", seed=0, total=80, spatial=90, circ=90, priv=90, env=90)
    b = _cand(cid="b", seed=1, total=70, spatial=80, circ=80, priv=80, env=80)
    assert dominates(a, b)
    assert not dominates(b, a)


def test_pareto_front_keeps_tradeoffs():
    # a: best spatial; b: best privacy; c: dominated by a on all
    a = _cand(cid="a", seed=0, total=85, spatial=95, circ=50, priv=40, env=40, x=0)
    b = _cand(cid="b", seed=1, total=80, spatial=40, circ=50, priv=95, env=40, x=5)
    c = _cand(cid="c", seed=2, total=70, spatial=30, circ=40, priv=30, env=30, x=10)
    front = pareto_front([a, b, c])
    ids = {x.id for x in front}
    assert ids == {"a", "b"}
    assert "c" not in ids


def test_select_pareto_slot1_is_global_top_score():
    """即使 crowding 更偏向低分极端点，slot1 仍是最高总分。"""
    # 最高分：轴中庸（易在纯 crowding 截断中落选）
    top = _cand(
        cid="top",
        seed=0,
        total=95.0,
        program=60.0,
        spatial=60.0,
        circ=60.0,
        priv=60.0,
        env=60.0,
        x=0,
    )
    extremes = [
        _cand(cid="p", seed=1, total=70, program=99, spatial=10, circ=10, priv=10, env=10, x=5),
        _cand(cid="s", seed=2, total=71, program=10, spatial=99, circ=10, priv=10, env=10, x=10),
        _cand(cid="c", seed=3, total=72, program=10, spatial=10, circ=99, priv=10, env=10, x=15),
        _cand(cid="v", seed=4, total=73, program=10, spatial=10, circ=10, priv=99, env=10, x=20),
        _cand(cid="e", seed=5, total=74, program=10, spatial=10, circ=10, priv=10, env=99, x=25),
    ]
    selected = select_pareto_frontier([top, *extremes], top_k=3)
    assert selected[0].id == "top"
    assert selected[0].metrics["selection_role"] == "top_score"
    assert selected[0].metrics["selection_label"] == "最高总分"
    assert len(selected) == 3
    assert all(c.id != "top" or i == 0 for i, c in enumerate(selected))
    for c in selected[1:]:
        assert c.metrics.get("selection_role") == "pareto"
        assert "效率" not in str(c.metrics.get("selection_label", ""))


def test_select_pareto_tags_and_truncates():
    cands = [
        _cand(cid="a", seed=0, total=90, spatial=90, circ=40, priv=40, env=40, x=0),
        _cand(cid="b", seed=1, total=80, spatial=40, circ=90, priv=40, env=40, x=6),
        _cand(cid="c", seed=2, total=78, spatial=40, circ=40, priv=90, env=40, x=12),
        _cand(cid="d", seed=3, total=76, spatial=40, circ=40, priv=40, env=90, x=18),
        _cand(cid="e", seed=4, total=50, spatial=10, circ=10, priv=10, env=10, x=24),
    ]
    selected = select_pareto_frontier(cands, top_k=3)
    assert len(selected) == 3
    assert selected[0].id == "a"
    assert selected[0].metrics.get("selection_role") == "top_score"
    assert all(c.metrics.get("selection_role") == "pareto" for c in selected[1:])
    assert all(c.id != "e" for c in selected)


def test_rank_mode_pareto_opt_in():
    cands = [
        _cand(cid="a", seed=0, total=90, spatial=90, circ=40, priv=40, env=40, x=0),
        _cand(cid="b", seed=1, total=80, spatial=40, circ=90, priv=40, env=40, x=8),
    ]
    ranked = rank_candidates(cands, top_k=2, mode="pareto")
    assert ranked[0].metrics.get("selection_role") == "top_score"
    assert ranked[1].metrics.get("selection_role") == "pareto"
    assert ranked[0].metrics.get("rank_mode") == "pareto"
    assert ranked[0].metrics.get("selection_version") == "pareto-top1-axes-v2"
    assert len(objective_vector(ranked[0])) == 5


def test_rank_mode_default_is_axis_not_pareto():
    cands = [
        _cand(cid="a", seed=0, total=90, spatial=90, circ=40, priv=40, env=40, x=0),
        _cand(cid="b", seed=1, total=80, spatial=40, circ=90, priv=40, env=40, x=8),
    ]
    ranked = rank_candidates(cands, top_k=2, min_diversity_threshold=0.5)
    assert ranked[0].metrics.get("rank_mode") == "axis"
    assert ranked[0].metrics.get("selection_version") == "axis-diversity-v1"
    assert ranked[0].metrics.get("selection_role") != "pareto"


def test_incomparable_pair_both_on_front():
    a = _cand(
        cid="a",
        seed=0,
        total=80,
        program=50,
        spatial=100,
        circ=0,
        priv=0,
        env=0,
        x=0,
    )
    b = _cand(
        cid="b",
        seed=1,
        total=80,
        program=50,
        spatial=0,
        circ=100,
        priv=0,
        env=0,
        x=5,
    )
    assert not dominates(a, b)
    assert not dominates(b, a)
    front = pareto_front([a, b])
    assert {c.id for c in front} == {"a", "b"}

"""Phase 8.2 — Pareto non-dominated selection。"""

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
    ev = DesignScore(
        total_score=total,
        program_score=total,
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


def test_dominates_basic():
    a = _cand(cid="a", seed=0, total=80, spatial=90, circ=90, priv=90, env=90)
    b = _cand(cid="b", seed=1, total=70, spatial=80, circ=80, priv=80, env=80)
    assert dominates(a, b)
    assert not dominates(b, a)


def test_pareto_front_keeps_tradeoffs():
    # a: best efficiency; b: best privacy; c: dominated by a on all
    a = _cand(cid="a", seed=0, total=85, spatial=95, circ=50, priv=40, env=40, x=0)
    b = _cand(cid="b", seed=1, total=80, spatial=40, circ=50, priv=95, env=40, x=5)
    c = _cand(cid="c", seed=2, total=70, spatial=30, circ=40, priv=30, env=30, x=10)
    front = pareto_front([a, b, c])
    ids = {x.id for x in front}
    assert ids == {"a", "b"}
    assert "c" not in ids


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
    assert all(c.metrics.get("selection_role") == "pareto" for c in selected)
    assert all(c.metrics.get("pareto_front") is True for c in selected)
    assert all(c.id != "e" for c in selected)


def test_rank_mode_pareto_opt_in():
    cands = [
        _cand(cid="a", seed=0, total=90, spatial=90, circ=40, priv=40, env=40, x=0),
        _cand(cid="b", seed=1, total=80, spatial=40, circ=90, priv=40, env=40, x=8),
    ]
    ranked = rank_candidates(cands, top_k=2, mode="pareto")
    assert ranked[0].metrics.get("selection_role") == "pareto"
    assert ranked[0].metrics.get("rank_mode") == "pareto"
    assert ranked[0].metrics.get("selection_version") == "pareto-crowding-v1"
    assert len(objective_vector(ranked[0])) == 4


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
    a = _cand(cid="a", seed=0, total=80, spatial=100, circ=0, priv=0, env=0, x=0)
    b = _cand(cid="b", seed=1, total=80, spatial=0, circ=100, priv=0, env=0, x=5)
    assert not dominates(a, b)
    assert not dominates(b, a)
    front = pareto_front([a, b])
    assert {c.id for c in front} == {"a", "b"}

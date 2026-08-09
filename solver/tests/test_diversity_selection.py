"""Phase 8.1 — top-score + axis diverse alternatives。"""

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
from solver.optimization.diversity_select import (
    select_diverse_alternatives,
)
from solver.optimization.rank import rank_candidates


def _cand(
    *,
    cid: str,
    seed: int,
    total: float,
    circ: float,
    priv: float,
    env: float = 50.0,
    x: float = 0.0,
) -> LayoutCandidate:
    """用不同 x 偏移制造几何差异（signature）。"""
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
        spatial_score=total,
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
        validation=CandidateValidation(valid=True, hard_violations=[], soft_violations=[]),
        metrics={},
    )


def test_top_score_always_first():
    cands = [
        _cand(cid="a", seed=0, total=80, circ=60, priv=60, x=0),
        _cand(cid="b", seed=1, total=90, circ=50, priv=50, x=5),
        _cand(cid="c", seed=2, total=70, circ=95, priv=40, x=10),
    ]
    selected = select_diverse_alternatives(
        cands, top_k=3, min_diversity_threshold=0.99
    )
    assert selected[0].id == "b"
    assert selected[0].metrics["selection_role"] == "top_score"
    assert selected[0].metrics["selection_label"] == "最高总分"


def test_circulation_alternative_when_clearly_better():
    top = _cand(cid="top", seed=0, total=90, circ=50, priv=50, x=0)
    circ = _cand(cid="circ", seed=1, total=85, circ=80, priv=40, x=8)
    other = _cand(cid="other", seed=2, total=84, circ=52, priv=40, x=16)
    selected = select_diverse_alternatives(
        [top, circ, other],
        top_k=3,
        min_diversity_threshold=0.99,
        axis_margin=2.0,
    )
    roles = {c.id: c.metrics.get("selection_role") for c in selected}
    assert roles["top"] == "top_score"
    assert roles["circ"] == "circulation"
    assert any(c.metrics.get("selection_label") == "流线更好" for c in selected)


def test_privacy_alternative():
    top = _cand(cid="top", seed=0, total=90, circ=70, priv=40, x=0)
    priv = _cand(cid="priv", seed=1, total=82, circ=50, priv=75, x=9)
    selected = select_diverse_alternatives(
        [top, priv],
        top_k=2,
        min_diversity_threshold=0.99,
        axis_margin=2.0,
    )
    assert selected[0].id == "top"
    assert selected[1].id == "priv"
    assert selected[1].metrics["selection_role"] == "privacy"


def test_no_axis_pick_when_not_better_than_top():
    top = _cand(cid="top", seed=0, total=90, circ=80, priv=80, x=0)
    weak = _cand(cid="weak", seed=1, total=85, circ=81, priv=81, x=10)
    # margin=2 → circ 81 < 80+2，不应作为 circulation 替代
    selected = select_diverse_alternatives(
        [top, weak],
        top_k=2,
        min_diversity_threshold=0.99,
        axis_margin=2.0,
    )
    assert selected[0].id == "top"
    assert selected[1].metrics["selection_role"] == "diverse"


def test_rank_candidates_tags_roles_by_default():
    cands = [
        _cand(cid="a", seed=0, total=90, circ=40, priv=40, x=0),
        _cand(cid="b", seed=1, total=80, circ=90, priv=30, x=7),
        _cand(cid="c", seed=2, total=78, circ=40, priv=95, x=14),
    ]
    ranked = rank_candidates(
        cands, top_k=3, min_diversity_threshold=0.5, mode="axis"
    )
    assert ranked[0].metrics.get("selection_role") == "top_score"
    roles = {c.metrics.get("selection_role") for c in ranked}
    assert "circulation" in roles or "privacy" in roles or "diverse" in roles


def test_rank_pure_score_when_diversity_disabled():
    cands = [
        _cand(cid="a", seed=0, total=70, circ=99, priv=99, x=0),
        _cand(cid="b", seed=1, total=90, circ=10, priv=10, x=5),
        _cand(cid="c", seed=2, total=80, circ=10, priv=10, x=10),
    ]
    ranked = rank_candidates(cands, top_k=2, min_diversity_threshold=None)
    assert [c.id for c in ranked] == ["b", "c"]
    assert ranked[0].metrics.get("rank_mode") == "score"
    assert ranked[0].metrics.get("selection_version") == "score-only-v1"
    assert "selection_role" not in ranked[0].metrics

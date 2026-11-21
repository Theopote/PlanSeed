"""优化会话质量键：Gate 优先于 private_through / score。"""

from __future__ import annotations

from packages.schema.layout import FloorLayout, LayoutCandidate
from solver.optimization.session import candidate_quality_key


def _cand(*, gate: bool, priv: int, score: float, cid: str = "c") -> LayoutCandidate:
    return LayoutCandidate(
        id=cid,
        seed=0,
        floors=[FloorLayout(floor_id="F1", placements=[])],
        score=score,
        metrics={
            "architectural_gate_pass": gate,
            "private_through_count": priv,
        },
    )


def test_gate_fail_never_ranks_above_gate_pass():
    good = _cand(gate=True, priv=2, score=70.0, cid="good")
    bad = _cand(gate=False, priv=0, score=95.0, cid="bad")
    assert candidate_quality_key(good) < candidate_quality_key(bad)

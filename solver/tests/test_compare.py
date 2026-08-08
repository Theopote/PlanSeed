"""候选确定性比较。"""

from __future__ import annotations

from packages.schema.scoring import DesignEvaluation, DesignFinding, FindingSeverity
from solver.evaluation.compare import compare_evaluations


def _ev(**scores: float) -> DesignEvaluation:
    return DesignEvaluation(
        program_score=scores.get("program", 80),
        spatial_score=scores.get("spatial", 80),
        circulation_score=scores.get("circulation", 80),
        privacy_score=scores.get("privacy", 80),
        environment_score=scores.get("environment", 80),
        technical_score=scores.get("technical", 80),
        robustness_score=scores.get("robustness", 80),
        total_score=scores.get("total", 80),
        findings=scores.get("findings", []) or [],
    )


def test_axis_advantage_by_margin():
    a = _ev(circulation=91, privacy=88, total=89)
    b = _ev(circulation=76, privacy=94, total=87)
    cmp = compare_evaluations(a, b, label_a="A", label_b="B")
    assert any("Circulation" in x or "交通" in x for x in cmp.advantages_a)
    assert any("Privacy" in x or "私密" in x for x in cmp.advantages_b)
    circ = next(r for r in cmp.rows if r.key == "circulation_score")
    assert circ.score_a == 91
    assert circ.score_b == 76


def test_positive_finding_unique():
    a = _ev(
        findings=[
            DesignFinding(
                id="circ.direct",
                category="circulation",
                severity=FindingSeverity.POSITIVE,
                title="交通更直接",
                message="入口到主要房间路径短",
            )
        ]
    )
    b = _ev()
    cmp = compare_evaluations(a, b)
    assert any("交通更直接" in x for x in cmp.advantages_a)


def test_deterministic_same_input():
    a = _ev(circulation=90, privacy=70)
    b = _ev(circulation=70, privacy=90)
    c1 = compare_evaluations(a, b)
    c2 = compare_evaluations(a, b)
    assert c1.advantages_a == c2.advantages_a
    assert c1.advantages_b == c2.advantages_b

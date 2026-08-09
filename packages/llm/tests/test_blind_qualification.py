"""Phase 6.7.2 — Blind Set 结构与 oracle 冒烟（不测真模型泛化）。"""

from packages.llm.benchmark import (
    BLIND_VERSION,
    blind_case_count,
    load_blind_cases,
    run_benchmark,
)
from packages.llm.benchmark.gates import evaluate_alpha_gates


def test_blind_has_at_least_40_unique_cases():
    cases = load_blind_cases()
    assert len(cases) >= 40
    assert blind_case_count() == len(cases)
    assert BLIND_VERSION.startswith("blind-")
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))
    assert all(c.id.startswith("bl") for c in cases)


def test_blind_covers_six_categories():
    tags = {t for c in load_blind_cases() for t in c.tags}
    for need in (
        "explicit",
        "intent",
        "access_near",
        "weak_pref",
        "negative",
        "ambiguous",
    ):
        assert need in tags, need


def test_blind_oracle_passes_alpha_gates():
    """Oracle 只证明 harness/gold；不代表 Blind 真模型泛化。"""
    cases = load_blind_cases()
    report = run_benchmark(
        use_oracle=True,
        cases=cases,
        case_set="blind",
        mode="oracle",
    )
    assert report.case_pass_rate == 1.0
    gate = evaluate_alpha_gates(report)
    assert gate.passed, [c for c in gate.checks if not c.passed]

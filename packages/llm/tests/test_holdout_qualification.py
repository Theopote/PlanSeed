"""Phase 6.7.1 — Holdout 语料与 Gate 扩展。"""

from packages.llm.benchmark import (
    HOLDOUT_VERSION,
    holdout_case_count,
    load_holdout_cases,
    run_benchmark,
)
from packages.llm.benchmark.gates import ALPHA_GATE_SPECS, evaluate_alpha_gates
from packages.llm.benchmark.report import BenchmarkReport
from packages.llm.benchmark.score import CaseScore


def test_holdout_has_at_least_30_unique_cases():
    cases = load_holdout_cases()
    assert len(cases) >= 30
    assert holdout_case_count() == len(cases)
    assert HOLDOUT_VERSION.startswith("holdout-")
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))
    assert all(c.id.startswith("ho-") for c in cases)


def test_holdout_oracle_passes_extended_alpha_gates():
    cases = load_holdout_cases()
    report = run_benchmark(
        use_oracle=True,
        cases=cases,
        case_set="holdout",
        mode="oracle",
    )
    assert report.case_pass_rate == 1.0
    gate = evaluate_alpha_gates(report)
    assert gate.passed, [c for c in gate.checks if not c.passed]
    keys = {s.key for s in ALPHA_GATE_SPECS}
    assert "relation_precision" in keys
    assert "unknown_precision" in keys
    assert "assumption_precision" in keys


def test_report_latency_percentiles_and_per_field():
    report = BenchmarkReport(
        case_scores=[
            CaseScore(case_id="a", latency_s=1.0),
            CaseScore(case_id="b", latency_s=2.0),
            CaseScore(case_id="c", latency_s=10.0),
        ],
        mode="pipeline",
        case_set="holdout",
    )
    s = report.summary()
    assert s["case_set"] == "holdout"
    assert s["latency_p50"] == 2.0
    assert s["max_latency"] == 10.0
    assert "floor_count_accuracy" in s
    assert "relation_precision" in s

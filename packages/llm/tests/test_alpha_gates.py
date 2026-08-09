from packages.llm.benchmark.gates import evaluate_alpha_gates
from packages.llm.benchmark import run_benchmark


def test_oracle_passes_alpha_gates():
    report = run_benchmark(use_oracle=True)
    gate = evaluate_alpha_gates(report)
    assert gate.passed
    assert gate.metrics["geometry_violation_rate"] == 0.0
    assert gate.metrics["parse_success_rate"] == 1.0
    assert gate.metrics["case_pass_rate"] == 1.0
    assert "relation_f1" in report.summary()


def test_geometry_gate_is_absolute():
    from packages.llm.benchmark.failure import FailureKind
    from packages.llm.benchmark.report import BenchmarkReport
    from packages.llm.benchmark.score import CaseScore

    report = BenchmarkReport(
        case_scores=[
            CaseScore(
                case_id="g1",
                geometry_fail=True,
                parse_failed=True,
                failure_kind=FailureKind.GEOMETRY_VIOLATION,
            ),
            CaseScore(case_id="g2"),
        ],
        mode="real",
        model="toy",
    )
    gate = evaluate_alpha_gates(report)
    geom = next(c for c in gate.checks if c.key == "geometry_violation_rate")
    assert not geom.passed
    assert not gate.passed

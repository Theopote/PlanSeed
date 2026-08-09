"""Phase 6.6–6.7.2 — Requirement Benchmark 包。"""

from packages.llm.benchmark.blind_cases_v2 import (
    BLIND_VERSION,
    blind_case_count,
    load_blind_cases,
)
from packages.llm.benchmark.cases import (
    ExpectAssumption,
    ExpectFloorPreference,
    ExpectKnown,
    ExpectOrientation,
    ExpectRelation,
    RequirementBenchmarkCase,
    benchmark_case_count,
    load_benchmark_cases,
)
from packages.llm.benchmark.failure import FailureKind
from packages.llm.benchmark.gates import (
    ALPHA_GATE_SPECS,
    AlphaGateResult,
    evaluate_alpha_gates,
    gate_metrics,
)
from packages.llm.benchmark.holdout_cases import (
    HOLDOUT_VERSION,
    holdout_case_count,
    load_holdout_cases,
)
from packages.llm.benchmark.report import BenchmarkReport
from packages.llm.benchmark.runner import (
    expect_to_draft,
    make_oracle_provider,
    run_benchmark,
    score_draft_against_case,
)
from packages.llm.benchmark.score import (
    AssumptionHit,
    CaseScore,
    FieldScore,
    RelationHit,
    score_requirement_case,
)

__all__ = [
    "ExpectAssumption",
    "ExpectFloorPreference",
    "ExpectKnown",
    "ExpectOrientation",
    "ExpectRelation",
    "RequirementBenchmarkCase",
    "ALPHA_GATE_SPECS",
    "AlphaGateResult",
    "BenchmarkReport",
    "FailureKind",
    "BLIND_VERSION",
    "HOLDOUT_VERSION",
    "AssumptionHit",
    "CaseScore",
    "FieldScore",
    "RelationHit",
    "benchmark_case_count",
    "blind_case_count",
    "evaluate_alpha_gates",
    "gate_metrics",
    "holdout_case_count",
    "load_benchmark_cases",
    "load_blind_cases",
    "load_holdout_cases",
    "expect_to_draft",
    "make_oracle_provider",
    "run_benchmark",
    "score_draft_against_case",
    "score_requirement_case",
]

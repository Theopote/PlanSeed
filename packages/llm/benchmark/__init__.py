"""Phase 6.6 — Requirement Benchmark 包。"""

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
    "BenchmarkReport",
    "FailureKind",
    "AssumptionHit",
    "CaseScore",
    "FieldScore",
    "RelationHit",
    "benchmark_case_count",
    "load_benchmark_cases",
    "expect_to_draft",
    "make_oracle_provider",
    "run_benchmark",
    "score_draft_against_case",
    "score_requirement_case",
]

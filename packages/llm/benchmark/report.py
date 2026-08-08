"""Requirement Benchmark 报告与汇总。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.llm.benchmark.score import CaseScore


@dataclass
class BenchmarkReport:
    case_scores: list[CaseScore] = field(default_factory=list)

    @property
    def case_count(self) -> int:
        return len(self.case_scores)

    @property
    def field_hits(self) -> int:
        return sum(c.field_hits for c in self.case_scores)

    @property
    def field_total(self) -> int:
        return sum(c.field_total for c in self.case_scores)

    @property
    def field_accuracy(self) -> float:
        if self.field_total == 0:
            return 1.0
        return self.field_hits / self.field_total

    @property
    def case_pass_rate(self) -> float:
        if not self.case_scores:
            return 1.0
        return sum(1 for c in self.case_scores if c.passed) / len(self.case_scores)

    @property
    def hallucination_rate(self) -> float:
        if not self.case_scores:
            return 0.0
        bad = sum(1 for c in self.case_scores if c.hallucinations)
        return bad / len(self.case_scores)

    @property
    def geometry_fails(self) -> int:
        return sum(1 for c in self.case_scores if c.geometry_fail)

    def summary(self) -> dict[str, float | int]:
        return {
            "case_count": self.case_count,
            "field_accuracy": round(self.field_accuracy, 4),
            "case_pass_rate": round(self.case_pass_rate, 4),
            "hallucination_rate": round(self.hallucination_rate, 4),
            "geometry_fails": self.geometry_fails,
            "field_hits": self.field_hits,
            "field_total": self.field_total,
        }

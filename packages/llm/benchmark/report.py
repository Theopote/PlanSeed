"""Requirement Benchmark 报告与汇总。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.llm.benchmark.score import CaseScore


@dataclass
class BenchmarkReport:
    case_scores: list[CaseScore] = field(default_factory=list)
    mode: str = "oracle"  # oracle | real
    model: str | None = None

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

    @property
    def geometry_fail_rate(self) -> float:
        if not self.case_scores:
            return 0.0
        return self.geometry_fails / len(self.case_scores)

    @property
    def parse_failures(self) -> int:
        return sum(1 for c in self.case_scores if c.parse_failed)

    @property
    def parse_failure_rate(self) -> float:
        if not self.case_scores:
            return 0.0
        return self.parse_failures / len(self.case_scores)

    @property
    def repair_rate(self) -> float:
        if not self.case_scores:
            return 0.0
        return sum(1 for c in self.case_scores if c.repaired) / len(self.case_scores)

    @property
    def average_attempts(self) -> float:
        if not self.case_scores:
            return 0.0
        return sum(c.attempts for c in self.case_scores) / len(self.case_scores)

    @property
    def average_latency_s(self) -> float:
        if not self.case_scores:
            return 0.0
        return sum(c.latency_s for c in self.case_scores) / len(self.case_scores)

    @property
    def relation_hits(self) -> int:
        return sum(c.relation_hits for c in self.case_scores)

    @property
    def relation_total(self) -> int:
        return sum(c.relation_total for c in self.case_scores)

    @property
    def relation_recall(self) -> float:
        if self.relation_total == 0:
            return 1.0
        return self.relation_hits / self.relation_total

    @property
    def relation_precision(self) -> float:
        """TP / 模型输出的关系条数（额外幻觉关系会拉低）。"""
        predicted = sum(c.relation_predicted for c in self.case_scores)
        if predicted == 0:
            return 1.0 if self.relation_total == 0 else 0.0
        return self.relation_hits / predicted

    @property
    def floor_pref_hits(self) -> int:
        return sum(1 for c in self.case_scores for f in c.floor_prefs if f.hit)

    @property
    def floor_pref_total(self) -> int:
        return sum(len(c.floor_prefs) for c in self.case_scores)

    @property
    def floor_preference_accuracy(self) -> float:
        if self.floor_pref_total == 0:
            return 1.0
        return self.floor_pref_hits / self.floor_pref_total

    @property
    def orientation_hits(self) -> int:
        return sum(1 for c in self.case_scores for f in c.orientations if f.hit)

    @property
    def orientation_total(self) -> int:
        return sum(len(c.orientations) for c in self.case_scores)

    @property
    def orientation_accuracy(self) -> float:
        if self.orientation_total == 0:
            return 1.0
        return self.orientation_hits / self.orientation_total

    @property
    def unknown_tp(self) -> int:
        return sum(c.unknown_tp for c in self.case_scores)

    @property
    def unknown_expected_total(self) -> int:
        return sum(len(c.unknown_expected) for c in self.case_scores)

    @property
    def unknown_predicted_total(self) -> int:
        return sum(len(c.unknown_predicted) for c in self.case_scores)

    @property
    def unknown_recall(self) -> float:
        if self.unknown_expected_total == 0:
            return 1.0
        return self.unknown_tp / self.unknown_expected_total

    @property
    def unknown_precision(self) -> float:
        if self.unknown_predicted_total == 0:
            return 1.0 if self.unknown_expected_total == 0 else 0.0
        return self.unknown_tp / self.unknown_predicted_total

    def summary(self) -> dict[str, float | int | str | None]:
        return {
            "mode": self.mode,
            "model": self.model,
            "case_count": self.case_count,
            "field_accuracy": round(self.field_accuracy, 4),
            "case_pass_rate": round(self.case_pass_rate, 4),
            "hallucination_rate": round(self.hallucination_rate, 4),
            "geometry_fail_rate": round(self.geometry_fail_rate, 4),
            "geometry_fails": self.geometry_fails,
            "parse_failure_rate": round(self.parse_failure_rate, 4),
            "repair_rate": round(self.repair_rate, 4),
            "average_attempts": round(self.average_attempts, 4),
            "average_latency_s": round(self.average_latency_s, 4),
            "relation_recall": round(self.relation_recall, 4),
            "relation_precision": round(self.relation_precision, 4),
            "floor_preference_accuracy": round(self.floor_preference_accuracy, 4),
            "orientation_accuracy": round(self.orientation_accuracy, 4),
            "unknown_precision": round(self.unknown_precision, 4),
            "unknown_recall": round(self.unknown_recall, 4),
            "field_hits": self.field_hits,
            "field_total": self.field_total,
        }

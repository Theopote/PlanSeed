"""Requirement Benchmark 报告与汇总。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.llm.benchmark.failure import FailureKind
from packages.llm.benchmark.score import CaseScore


@dataclass
class BenchmarkReport:
    case_scores: list[CaseScore] = field(default_factory=list)
    mode: str = "oracle"  # oracle | real | pipeline | model_raw
    model: str | None = None
    case_set: str = "development"  # development | holdout

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

    def _latency_percentile(self, p: float) -> float:
        if not self.case_scores:
            return 0.0
        xs = sorted(c.latency_s for c in self.case_scores)
        if len(xs) == 1:
            return xs[0]
        # nearest-rank
        k = max(0, min(len(xs) - 1, int(round(p * (len(xs) - 1)))))
        return xs[k]

    @property
    def latency_p50(self) -> float:
        return self._latency_percentile(0.50)

    @property
    def latency_p90(self) -> float:
        return self._latency_percentile(0.90)

    @property
    def latency_p95(self) -> float:
        return self._latency_percentile(0.95)

    @property
    def max_latency(self) -> float:
        if not self.case_scores:
            return 0.0
        return max(c.latency_s for c in self.case_scores)

    def _field_accuracy_named(self, name: str) -> float:
        hits = 0
        total = 0
        for c in self.case_scores:
            for f in c.fields:
                if f.name != name:
                    continue
                total += 1
                if f.hit:
                    hits += 1
        if total == 0:
            return 1.0
        return hits / total

    @property
    def floor_count_accuracy(self) -> float:
        return self._field_accuracy_named("floor_count")

    @property
    def bedrooms_accuracy(self) -> float:
        return self._field_accuracy_named("bedrooms")

    @property
    def bathrooms_accuracy(self) -> float:
        return self._field_accuracy_named("bathrooms")

    @property
    def site_width_accuracy(self) -> float:
        return self._field_accuracy_named("site_width")

    @property
    def site_depth_accuracy(self) -> float:
        return self._field_accuracy_named("site_depth")

    @property
    def garage_accuracy(self) -> float:
        return self._field_accuracy_named("has_garage")

    @property
    def south_orientation_accuracy(self) -> float:
        return self._field_accuracy_named("prefer_south_facing_living")

    @property
    def schema_fails(self) -> int:
        return sum(
            1
            for c in self.case_scores
            if c.failure_kind == FailureKind.SCHEMA_FAIL
        )

    @property
    def semantic_fails(self) -> int:
        return sum(
            1
            for c in self.case_scores
            if c.failure_kind == FailureKind.SEMANTIC_FAIL
        )

    @property
    def geometry_violations(self) -> int:
        """按 failure_kind 统计；与 geometry_fails（legacy flag）互补。"""
        return sum(
            1
            for c in self.case_scores
            if c.failure_kind == FailureKind.GEOMETRY_VIOLATION or c.geometry_fail
        )

    @property
    def json_parse_fails(self) -> int:
        return sum(
            1
            for c in self.case_scores
            if c.failure_kind == FailureKind.JSON_PARSE_FAIL
        )

    @property
    def repair_successes(self) -> int:
        return sum(1 for c in self.case_scores if c.repair_success)

    @property
    def repair_exhausted_count(self) -> int:
        return sum(1 for c in self.case_scores if c.repair_exhausted)

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
    def relation_f1(self) -> float:
        p = self.relation_precision
        r = self.relation_recall
        if p + r <= 0:
            return 1.0 if self.relation_total == 0 else 0.0
        return 2.0 * p * r / (p + r)

    @property
    def parse_success_rate(self) -> float:
        return 1.0 - self.parse_failure_rate

    @property
    def repair_exhausted_rate(self) -> float:
        if not self.case_scores:
            return 0.0
        return self.repair_exhausted_count / len(self.case_scores)

    @property
    def geometry_violation_rate(self) -> float:
        if not self.case_scores:
            return 0.0
        return self.geometry_violations / len(self.case_scores)

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
        """Unknown Detection Recall：must_unknown 被列入 unknowns 的比例。"""
        if self.unknown_expected_total == 0:
            return 1.0
        return self.unknown_tp / self.unknown_expected_total

    @property
    def unknown_detection_recall(self) -> float:
        return self.unknown_recall

    @property
    def unknown_precision(self) -> float:
        if self.unknown_predicted_total == 0:
            return 1.0 if self.unknown_expected_total == 0 else 0.0
        return self.unknown_tp / self.unknown_predicted_total

    @property
    def unknown_false_positive_rate(self) -> float:
        """列入 unknowns 但不在 must_unknown 中的比例（相对预测集）。"""
        if self.unknown_predicted_total == 0:
            return 0.0
        fp = sum(len(c.unknown_false_positives) for c in self.case_scores)
        return fp / self.unknown_predicted_total

    @property
    def assumption_tp(self) -> int:
        return sum(c.assumption_hits for c in self.case_scores)

    @property
    def assumption_expected_total(self) -> int:
        return sum(c.assumption_total for c in self.case_scores)

    @property
    def assumption_predicted_total(self) -> int:
        return sum(c.assumption_predicted for c in self.case_scores)

    @property
    def assumption_precision(self) -> float:
        """
        Assumption Precision：预测 assumptions 中命中期望的比例。

        无期望且无预测 → 1.0；有预测无期望 → 0.0（多余假设视为 FP）。
        """
        predicted = self.assumption_predicted_total
        if predicted == 0:
            return 1.0 if self.assumption_expected_total == 0 else 0.0
        return self.assumption_tp / predicted

    @property
    def assumption_recall(self) -> float:
        if self.assumption_expected_total == 0:
            return 1.0
        return self.assumption_tp / self.assumption_expected_total

    def summary(self) -> dict[str, float | int | str | None]:
        return {
            "mode": self.mode,
            "case_set": self.case_set,
            "model": self.model,
            "case_count": self.case_count,
            "field_accuracy": round(self.field_accuracy, 4),
            "floor_count_accuracy": round(self.floor_count_accuracy, 4),
            "bedrooms_accuracy": round(self.bedrooms_accuracy, 4),
            "bathrooms_accuracy": round(self.bathrooms_accuracy, 4),
            "site_width_accuracy": round(self.site_width_accuracy, 4),
            "site_depth_accuracy": round(self.site_depth_accuracy, 4),
            "garage_accuracy": round(self.garage_accuracy, 4),
            "south_orientation_accuracy": round(self.south_orientation_accuracy, 4),
            "case_pass_rate": round(self.case_pass_rate, 4),
            "hallucination_rate": round(self.hallucination_rate, 4),
            "geometry_fail_rate": round(self.geometry_fail_rate, 4),
            "geometry_fails": self.geometry_fails,
            "geometry_violation_rate": round(self.geometry_violation_rate, 4),
            "parse_failure_rate": round(self.parse_failure_rate, 4),
            "parse_success_rate": round(self.parse_success_rate, 4),
            "repair_rate": round(self.repair_rate, 4),
            "schema_fail": self.schema_fails,
            "semantic_fail": self.semantic_fails,
            "geometry_violation": self.geometry_violations,
            "json_parse_fail": self.json_parse_fails,
            "repair_success": self.repair_successes,
            "repair_exhausted": self.repair_exhausted_count,
            "repair_exhausted_rate": round(self.repair_exhausted_rate, 4),
            "average_attempts": round(self.average_attempts, 4),
            "average_latency_s": round(self.average_latency_s, 4),
            "latency_p50": round(self.latency_p50, 4),
            "latency_p90": round(self.latency_p90, 4),
            "latency_p95": round(self.latency_p95, 4),
            "max_latency": round(self.max_latency, 4),
            "relation_recall": round(self.relation_recall, 4),
            "relation_precision": round(self.relation_precision, 4),
            "relation_f1": round(self.relation_f1, 4),
            "floor_preference_accuracy": round(self.floor_preference_accuracy, 4),
            "orientation_accuracy": round(self.orientation_accuracy, 4),
            "unknown_detection_recall": round(self.unknown_detection_recall, 4),
            "unknown_precision": round(self.unknown_precision, 4),
            "unknown_false_positive_rate": round(self.unknown_false_positive_rate, 4),
            "assumption_precision": round(self.assumption_precision, 4),
            "assumption_recall": round(self.assumption_recall, 4),
            "field_hits": self.field_hits,
            "field_total": self.field_total,
        }

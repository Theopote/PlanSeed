"""Phase 6.7 — PlanSeed Alpha 内部门槛（非行业标准）。

唯一接近绝对要求的是 Geometry violation = 0（架构边界）。
其余为务实 Alpha Gate；达到后才可写 Phase 6 ✅ Alpha Qualified。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from packages.llm.benchmark.report import BenchmarkReport

Cmp = Literal["eq", "le", "ge"]


@dataclass(frozen=True)
class AlphaGateSpec:
    key: str
    label: str
    threshold: float
    cmp: Cmp
    note: str = ""


# PlanSeed Alpha 内部门槛（用户建议 · 十七/十八）
ALPHA_GATE_SPECS: tuple[AlphaGateSpec, ...] = (
    AlphaGateSpec(
        "geometry_violation_rate",
        "Geometry violation",
        0.0,
        "eq",
        "架构边界：应接近绝对要求",
    ),
    AlphaGateSpec(
        "parse_success_rate",
        "Parse success",
        0.95,
        "ge",
    ),
    AlphaGateSpec(
        "field_accuracy",
        "Scalar field accuracy",
        0.90,
        "ge",
    ),
    AlphaGateSpec(
        "relation_f1",
        "Relation F1",
        0.80,
        "ge",
    ),
    AlphaGateSpec(
        "hallucination_rate",
        "Unknown hallucination",
        0.05,
        "le",
    ),
    AlphaGateSpec(
        "repair_exhausted_rate",
        "Repair exhausted",
        0.05,
        "le",
    ),
    AlphaGateSpec(
        "case_pass_rate",
        "Case pass rate",
        0.70,
        "ge",
    ),
)


@dataclass(frozen=True)
class GateCheck:
    key: str
    label: str
    actual: float
    threshold: float
    cmp: Cmp
    passed: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "actual": round(self.actual, 4),
            "threshold": self.threshold,
            "cmp": self.cmp,
            "passed": self.passed,
            "note": self.note,
        }


@dataclass(frozen=True)
class AlphaGateResult:
    checks: tuple[GateCheck, ...]
    metrics: dict[str, float]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
        }


def _cmp(actual: float, threshold: float, op: Cmp) -> bool:
    if op == "eq":
        return abs(actual - threshold) < 1e-9
    if op == "le":
        return actual <= threshold + 1e-12
    if op == "ge":
        return actual >= threshold - 1e-12
    raise ValueError(f"未知比较符 {op!r}")


def gate_metrics(report: BenchmarkReport) -> dict[str, float]:
    """从 BenchmarkReport 导出 Alpha Gate 用指标。"""
    return {
        "geometry_violation_rate": report.geometry_violation_rate,
        "parse_success_rate": report.parse_success_rate,
        "field_accuracy": report.field_accuracy,
        "relation_f1": report.relation_f1,
        "hallucination_rate": report.hallucination_rate,
        "repair_exhausted_rate": report.repair_exhausted_rate,
        "case_pass_rate": report.case_pass_rate,
        "relation_precision": report.relation_precision,
        "relation_recall": report.relation_recall,
    }


def evaluate_alpha_gates(report: BenchmarkReport) -> AlphaGateResult:
    """对照 ALPHA_GATE_SPECS 判定是否 Alpha Qualified。"""
    metrics = gate_metrics(report)
    checks: list[GateCheck] = []
    for spec in ALPHA_GATE_SPECS:
        actual = metrics[spec.key]
        checks.append(
            GateCheck(
                key=spec.key,
                label=spec.label,
                actual=actual,
                threshold=spec.threshold,
                cmp=spec.cmp,
                passed=_cmp(actual, spec.threshold, spec.cmp),
                note=spec.note,
            )
        )
    return AlphaGateResult(checks=tuple(checks), metrics=metrics)

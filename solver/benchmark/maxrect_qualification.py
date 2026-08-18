"""MaxRect product qualification gate — Layout Benchmark Suite v1。

基于跨 case 统计判定 MaxRect 是否可进入 Alpha candidate pool。
实现完成 ≠ 产品验收；本模块只读 benchmark 报告产出 gate 结论。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from packages.schema.identity import SOLVER_VERSION

from solver.benchmark.layout_generation import (
    LayoutGenerationBenchmarkReport,
    LayoutSuiteBenchmarkReport,
)

GATE_ID = "maxrect-suite-v1-gate"
GATE_VERSION = "v1"

# 门槛（可 bump gate version 时调整）
VALID_RATE_DROP_MAX = 0.05
ASPECT_PENALTY_RATIO_MAX = 3.0
AGGREGATE_ASPECT_PENALTY_RATIO_MAX = 2.5
LOCKS_CASE_IDS = frozenset({"B11", "B12"})
MIN_LOCKS_VALID_RATE = 0.5
AGGREGATE_TOP_SCORE_RATIO_MIN = 0.92
MIN_CASE_VALID_RATE = 0.8


@dataclass(frozen=True)
class CaseQualification:
    case_id: str
    passed: bool
    valid_rate_guillotine: float
    valid_rate_maxrect: float
    aspect_penalty_guillotine: float
    aspect_penalty_maxrect: float
    aspect_penalty_ratio: float | None
    top_score_guillotine: float
    top_score_maxrect: float
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MaxRectQualificationReport:
    gate_id: str = GATE_ID
    gate_version: str = GATE_VERSION
    solver_version: str = SOLVER_VERSION
    suite_id: str = ""
    suite_version: str = ""
    candidate_count: int = 0
    passed: bool = False
    case_results: list[CaseQualification] = field(default_factory=list)
    aggregate_aspect_penalty_ratio: float | None = None
    aggregate_top_score_ratio: float | None = None
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_version": self.gate_version,
            "solver_version": self.solver_version,
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "candidate_count": self.candidate_count,
            "passed": self.passed,
            "case_results": [c.to_dict() for c in self.case_results],
            "aggregate_aspect_penalty_ratio": self.aggregate_aspect_penalty_ratio,
            "aggregate_top_score_ratio": self.aggregate_top_score_ratio,
            "failures": list(self.failures),
            "notes": list(self.notes),
        }


def _strategy_metrics(
    case: LayoutGenerationBenchmarkReport,
    strategy_id: str,
) -> dict[str, float] | None:
    for s in case.strategies:
        if s.strategy_id == strategy_id:
            return s.to_dict()
    return None


def _aspect_penalty_ratio(g_pen: float, m_pen: float) -> float | None:
    if g_pen <= 1e-9:
        return None if m_pen <= 1e-9 else float("inf")
    return m_pen / g_pen


def evaluate_case(case: LayoutGenerationBenchmarkReport) -> CaseQualification:
    g = _strategy_metrics(case, "guillotine")
    m = _strategy_metrics(case, "maxrect")
    failures: list[str] = []
    if g is None or m is None:
        failures.append("missing strategy metrics")
        return CaseQualification(
            case_id=case.case,
            passed=False,
            valid_rate_guillotine=0.0,
            valid_rate_maxrect=0.0,
            aspect_penalty_guillotine=0.0,
            aspect_penalty_maxrect=0.0,
            aspect_penalty_ratio=None,
            top_score_guillotine=0.0,
            top_score_maxrect=0.0,
            failures=tuple(failures),
        )

    g_vr = float(g["valid_rate"])
    m_vr = float(m["valid_rate"])
    g_pen = float(g["mean_aspect_ratio_penalty"])
    m_pen = float(m["mean_aspect_ratio_penalty"])
    g_top = float(g["top_score"])
    m_top = float(m["top_score"])
    ratio = _aspect_penalty_ratio(g_pen, m_pen)

    if g_vr < MIN_CASE_VALID_RATE and m_vr < MIN_CASE_VALID_RATE:
        failures.append(
            f"both strategies valid_rate < {MIN_CASE_VALID_RATE} (case may be unsolvable at n={case.candidate_count})"
        )

    if m_vr < g_vr - VALID_RATE_DROP_MAX:
        failures.append(
            f"valid_rate drop {g_vr:.3f}→{m_vr:.3f} "
            f"(max drop {VALID_RATE_DROP_MAX})"
        )
    if m_vr < MIN_CASE_VALID_RATE and g_vr >= MIN_CASE_VALID_RATE:
        failures.append(f"valid_rate {m_vr:.3f} < {MIN_CASE_VALID_RATE}")

    if ratio is not None and ratio > ASPECT_PENALTY_RATIO_MAX:
        failures.append(
            f"aspect_penalty ratio {ratio:.2f} > {ASPECT_PENALTY_RATIO_MAX}"
        )

    if case.case in LOCKS_CASE_IDS and m_vr < MIN_LOCKS_VALID_RATE:
        failures.append(
            f"locks case valid_rate {m_vr:.3f} < {MIN_LOCKS_VALID_RATE}"
        )

    return CaseQualification(
        case_id=case.case,
        passed=not failures,
        valid_rate_guillotine=g_vr,
        valid_rate_maxrect=m_vr,
        aspect_penalty_guillotine=g_pen,
        aspect_penalty_maxrect=m_pen,
        aspect_penalty_ratio=round(ratio, 4) if ratio is not None and ratio != float("inf") else ratio,
        top_score_guillotine=g_top,
        top_score_maxrect=m_top,
        failures=tuple(failures),
    )


def evaluate_maxrect_qualification(
    suite_report: LayoutSuiteBenchmarkReport,
) -> MaxRectQualificationReport:
    """对 Suite v1 报告运行 MaxRect qualification gate。"""
    case_results = [evaluate_case(c) for c in suite_report.cases]
    failures: list[str] = []

    agg = suite_report.aggregate
    g_agg = agg.get("guillotine", {})
    m_agg = agg.get("maxrect", {})
    agg_pen_ratio: float | None = None
    agg_top_ratio: float | None = None

    if g_agg and m_agg:
        agg_pen_ratio = _aspect_penalty_ratio(
            float(g_agg.get("mean_aspect_ratio_penalty", 0.0)),
            float(m_agg.get("mean_aspect_ratio_penalty", 0.0)),
        )
        g_top = float(g_agg.get("top_score", 0.0))
        m_top = float(m_agg.get("top_score", 0.0))
        if g_top > 1e-9:
            agg_top_ratio = m_top / g_top

        if agg_pen_ratio is not None and agg_pen_ratio > AGGREGATE_ASPECT_PENALTY_RATIO_MAX:
            failures.append(
                f"aggregate aspect_penalty ratio {agg_pen_ratio:.2f} "
                f"> {AGGREGATE_ASPECT_PENALTY_RATIO_MAX}"
            )
        if agg_top_ratio is not None and agg_top_ratio < AGGREGATE_TOP_SCORE_RATIO_MIN:
            failures.append(
                f"aggregate top_score ratio {agg_top_ratio:.3f} "
                f"< {AGGREGATE_TOP_SCORE_RATIO_MIN}"
            )

    for cr in case_results:
        if not cr.passed:
            for msg in cr.failures:
                failures.append(f"{cr.case_id}: {msg}")

    passed = not failures
    return MaxRectQualificationReport(
        gate_id=GATE_ID,
        gate_version=GATE_VERSION,
        solver_version=SOLVER_VERSION,
        suite_id=suite_report.suite_id,
        suite_version=suite_report.suite_version,
        candidate_count=suite_report.candidate_count,
        passed=passed,
        case_results=case_results,
        aggregate_aspect_penalty_ratio=(
            round(agg_pen_ratio, 4)
            if agg_pen_ratio is not None and agg_pen_ratio != float("inf")
            else agg_pen_ratio
        ),
        aggregate_top_score_ratio=(
            round(agg_top_ratio, 4) if agg_top_ratio is not None else None
        ),
        failures=failures,
        notes=[
            "passed=True 才可讨论混入 Alpha candidate pool",
            "Alpha 默认仍为 Guillotine only until gate passes + product sign-off",
            f"thresholds: valid_drop<={VALID_RATE_DROP_MAX}, "
            f"case_aspect_ratio<={ASPECT_PENALTY_RATIO_MAX}, "
            f"agg_aspect_ratio<={AGGREGATE_ASPECT_PENALTY_RATIO_MAX}",
        ],
    )


def format_qualification_report(report: MaxRectQualificationReport) -> str:
    lines = [
        f"maxrect-qualification  gate={report.gate_id}  "
        f"solver={report.solver_version}  n={report.candidate_count}  "
        f"PASSED={report.passed}",
    ]
    if report.aggregate_aspect_penalty_ratio is not None:
        lines.append(
            f"aggregate aspect_penalty ratio (maxrect/guillotine): "
            f"{report.aggregate_aspect_penalty_ratio}"
        )
    if report.aggregate_top_score_ratio is not None:
        lines.append(
            f"aggregate top_score ratio (maxrect/guillotine): "
            f"{report.aggregate_top_score_ratio}"
        )
    lines.append("")
    lines.append("case | pass | valid G/M | asp_pen G/M | ratio | top G/M")
    for c in report.case_results:
        ratio_s = (
            f"{c.aspect_penalty_ratio:.2f}"
            if c.aspect_penalty_ratio is not None
            and c.aspect_penalty_ratio != float("inf")
            else "—"
        )
        lines.append(
            f"{c.case_id} | {'OK' if c.passed else 'FAIL'} | "
            f"{c.valid_rate_guillotine:.3f}/{c.valid_rate_maxrect:.3f} | "
            f"{c.aspect_penalty_guillotine:.1f}/{c.aspect_penalty_maxrect:.1f} | "
            f"{ratio_s} | {c.top_score_guillotine:.1f}/{c.top_score_maxrect:.1f}"
        )
    if report.failures:
        lines.append("")
        lines.append("failures:")
        for f in report.failures:
            lines.append(f"  - {f}")
    return "\n".join(lines)

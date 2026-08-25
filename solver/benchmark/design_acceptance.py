"""Design Benchmark v2 harness — 建筑师可接受性评价。

主指标：ab_rate = (count_A + count_B) / candidates_generated
规格：docs/design-benchmark-v2.md
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from packages.schema.identity import SOLVER_VERSION
from packages.schema.program import DesignProgram

from solver.benchmark.layout_generation import (
    _geom_fingerprint,
    _mean,
    run_strategy_benchmark,
)
from solver.fixtures.design_suite_v2 import (
    SUITE_ID,
    SUITE_VERSION,
    DesignSuiteCase,
    iter_suite_cases,
    list_suite_case_ids,
)
from solver.generators.guillotine import GuillotineGenerator
from solver.visualize.svg import write_candidate_svg

ArchitectGrade = Literal["A", "B", "C", "D"]
_AB_GRADES = frozenset({"A", "B"})


@dataclass
class CandidateAcceptanceRecord:
    index: int
    seed: int
    valid: bool
    auto_grade: str
    fingerprint: str
    total_score: float
    axis_scores: dict[str, float]
    metrics_proxy: dict[str, float | int]
    findings_summary: list[dict[str, Any]]
    hard_violation_count: int
    human_grade: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DesignCaseAcceptanceReport:
    case_id: str
    case_title: str
    tier: str
    focus_metrics: list[str]
    d_grade_hints: list[str]
    candidate_count: int
    valid_count: int
    valid_rate: float
    ab_rate: float | None
    grade_counts: dict[str, int]
    runtime_s: float
    strategy_id: str
    generator_version: str
    candidates: list[CandidateAcceptanceRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_title": self.case_title,
            "tier": self.tier,
            "focus_metrics": self.focus_metrics,
            "d_grade_hints": self.d_grade_hints,
            "candidate_count": self.candidate_count,
            "valid_count": self.valid_count,
            "valid_rate": self.valid_rate,
            "ab_rate": self.ab_rate,
            "grade_counts": self.grade_counts,
            "runtime_s": self.runtime_s,
            "strategy_id": self.strategy_id,
            "generator_version": self.generator_version,
            "candidates": [c.to_dict() for c in self.candidates],
        }


@dataclass
class DesignSuiteAcceptanceReport:
    suite_id: str = SUITE_ID
    suite_version: str = SUITE_VERSION
    solver_version: str = SOLVER_VERSION
    candidate_count: int = 32
    measured_at: str = ""
    wave: str = "core"
    cases: list[DesignCaseAcceptanceReport] = field(default_factory=list)
    aggregate: dict[str, float] = field(default_factory=dict)
    grades_merged: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "solver_version": self.solver_version,
            "candidate_count": self.candidate_count,
            "measured_at": self.measured_at,
            "wave": self.wave,
            "cases": [c.to_dict() for c in self.cases],
            "aggregate": self.aggregate,
            "grades_merged": self.grades_merged,
            "notes": list(self.notes),
        }


def _axis_scores(candidate: Any) -> dict[str, float]:
    if candidate.evaluation is None:
        return {}
    ev = candidate.evaluation
    return {
        "program": float(ev.program_score),
        "spatial": float(ev.spatial_score),
        "circulation": float(ev.circulation_score),
        "privacy": float(ev.privacy_score),
        "environment": float(ev.environment_score),
        "technical": float(ev.technical_score),
        "robustness": float(ev.robustness_score),
        "total": float(ev.total_score),
    }


def _metrics_proxy(candidate: Any) -> dict[str, float | int]:
    m = candidate.metrics
    ev = candidate.evaluation
    proxy: dict[str, float | int] = {
        "area_accuracy": float(m.get("area_accuracy", 0.0)),
        "aspect_ratio_penalty": float(m.get("aspect_ratio_penalty", 0.0)),
        "slender_room_count": int(m.get("slender_room_count", 0) or 0),
        "reachable_ratio": float(m.get("reachable_ratio", 0.0)),
        "connection_repairs": float(m.get("connection_repairs", 0.0) or 0.0),
        "required_adjacency_satisfaction": float(
            m.get("required_adjacency_satisfaction", 0.0)
        ),
        "wet_stack_alignment": float(m.get("wet_stack_alignment", 0.0)),
    }
    if ev is not None:
        proxy["orientation_satisfaction"] = float(
            ev.metrics.orientation_satisfaction
        )
    for key in ("setback_compliance", "entry_on_road", "garage_on_road"):
        if key in m:
            proxy[key] = float(m[key])
    return proxy


def _findings_summary(candidate: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    if candidate.evaluation is None:
        return []
    severity_order = {"problem": 0, "warning": 1, "info": 2, "positive": 3}
    findings = sorted(
        candidate.evaluation.findings,
        key=lambda f: (severity_order.get(str(f.severity), 9), f.id),
    )
    out: list[dict[str, Any]] = []
    for f in findings[:limit]:
        out.append(
            {
                "id": f.id,
                "category": f.category,
                "severity": str(f.severity),
                "title": f.title,
                "room_ids": list(f.room_ids),
            }
        )
    return out


def _candidate_seed(program: DesignProgram, index: int) -> int:
    return program.solver_config.base_seed + index


def _record_candidate(
    candidate: Any,
    *,
    index: int,
    program: DesignProgram,
) -> CandidateAcceptanceRecord:
    hard_n = 0
    valid = False
    if candidate.validation is not None:
        hard_n = len(candidate.validation.hard_violations)
        valid = bool(candidate.validation.valid)
    total = 0.0
    if candidate.score is not None:
        total = float(candidate.score)
    elif candidate.evaluation is not None:
        total = float(candidate.evaluation.total_score)
    return CandidateAcceptanceRecord(
        index=index,
        seed=_candidate_seed(program, index),
        valid=valid,
        auto_grade="D" if not valid else "",
        fingerprint=_geom_fingerprint(candidate),
        total_score=round(total, 2),
        axis_scores=_axis_scores(candidate),
        metrics_proxy=_metrics_proxy(candidate),
        findings_summary=_findings_summary(candidate),
        hard_violation_count=hard_n,
    )


def _grade_counts(candidates: list[CandidateAcceptanceRecord]) -> dict[str, int]:
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for c in candidates:
        g = c.human_grade or c.auto_grade or "D"
        if g not in counts:
            g = "D"
        counts[g] += 1
    return counts


def compute_ab_rate(candidates: list[CandidateAcceptanceRecord]) -> float:
    if not candidates:
        return 0.0
    ab = sum(
        1
        for c in candidates
        if (c.human_grade or c.auto_grade or "D") in _AB_GRADES
    )
    return round(ab / len(candidates), 4)


def merge_grades(
    report: DesignSuiteAcceptanceReport,
    grades_path: Path | str,
) -> DesignSuiteAcceptanceReport:
    """将人工 grades.json 合并进报告并重算 ab_rate。"""
    path = Path(grades_path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    grades_by_case: dict[str, dict[str, Any]] = data.get("grades", {})
    for case in report.cases:
        case_grades = grades_by_case.get(case.case_id, {})
        for cand in case.candidates:
            entry = case_grades.get(str(cand.index))
            if entry is None:
                continue
            grade = str(entry.get("grade", "")).upper()
            if grade in ("A", "B", "C", "D"):
                cand.human_grade = grade
        case.grade_counts = _grade_counts(case.candidates)
        case.ab_rate = compute_ab_rate(case.candidates)
    report.grades_merged = True
    ab_rates = [c.ab_rate for c in report.cases if c.ab_rate is not None]
    report.aggregate["ab_rate"] = round(_mean(ab_rates), 4) if ab_rates else 0.0
    valid_rates = [c.valid_rate for c in report.cases]
    report.aggregate["valid_rate"] = round(_mean(valid_rates), 4)
    return report


def export_case_svgs(
    suite_case: DesignSuiteCase,
    pipeline_result: Any,
    out_dir: Path,
    *,
    program: DesignProgram,
) -> list[Path]:
    """导出每 candidate 的 SVG（按 index 命名）。"""
    case_dir = out_dir / suite_case.meta.id
    case_dir.mkdir(parents=True, exist_ok=True)
    site = program.site
    floor_labels = {f.id: f.label for f in program.floors}
    target_areas = {r.id: r.target_area for r in program.rooms}
    written: list[Path] = []
    for i, cand in enumerate(pipeline_result.all_candidates):
        path = case_dir / f"candidate_{i:03d}.svg"
        write_candidate_svg(
            cand,
            path,
            floor_width=site.width,
            floor_depth=site.depth,
            floor_labels=floor_labels,
            target_areas=target_areas,
            site=site,
            access_graph=program.access_graph,
            render_mode="customer",
        )
        written.append(path)
    return written


def run_design_case_acceptance(
    suite_case: DesignSuiteCase,
    *,
    candidate_count: int = 32,
    export_svg_dir: Path | None = None,
) -> DesignCaseAcceptanceReport:
    generator = GuillotineGenerator()
    t0 = time.perf_counter()
    metrics, result = run_strategy_benchmark(
        generator,
        suite_case.program,
        candidate_count=candidate_count,
    )
    runtime = time.perf_counter() - t0

    records = [
        _record_candidate(c, index=i, program=suite_case.program)
        for i, c in enumerate(result.all_candidates)
    ]
    valid_count = sum(1 for r in records if r.valid)

    if export_svg_dir is not None:
        export_case_svgs(
            suite_case,
            result,
            export_svg_dir,
            program=suite_case.program,
        )

    return DesignCaseAcceptanceReport(
        case_id=suite_case.meta.id,
        case_title=suite_case.meta.title,
        tier=suite_case.meta.tier,
        focus_metrics=list(suite_case.meta.focus_metrics),
        d_grade_hints=list(suite_case.meta.d_grade_hints),
        candidate_count=len(records),
        valid_count=valid_count,
        valid_rate=round(valid_count / max(1, len(records)), 4),
        ab_rate=None,
        grade_counts=_grade_counts(records),
        runtime_s=round(runtime, 4),
        strategy_id=metrics.strategy_id,
        generator_version=metrics.generator_version,
        candidates=records,
    )


def run_design_suite_acceptance(
    *,
    candidate_count: int = 32,
    case_ids: list[str] | None = None,
    export_svg_dir: Path | None = None,
    grades_path: Path | str | None = None,
) -> DesignSuiteAcceptanceReport:
    cases = iter_suite_cases(case_ids)
    reports: list[DesignCaseAcceptanceReport] = []
    for sc in cases:
        reports.append(
            run_design_case_acceptance(
                sc,
                candidate_count=candidate_count,
                export_svg_dir=export_svg_dir,
            )
        )
    suite = DesignSuiteAcceptanceReport(
        candidate_count=candidate_count,
        measured_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        cases=reports,
        aggregate={
            "valid_rate": round(_mean([c.valid_rate for c in reports]), 4),
        },
        notes=[
            "primary metric: ab_rate = (A+B)/candidates_generated (requires --merge-grades)",
            "invalid candidates auto-grade D",
            "strategy: guillotine only (Alpha default)",
            "wave 1: core B01-B07; wave 2: site B08-B12",
        ],
    )
    if grades_path is not None:
        merge_grades(suite, grades_path)
    return suite


def format_acceptance_table(report: DesignSuiteAcceptanceReport) -> str:
    headers = [
        "case",
        "tier",
        "valid",
        "valid_n",
        "top",
        "circ",
        "priv",
        "D_auto",
        "ab_rate",
    ]
    rows: list[list[str]] = [headers]
    for case in report.cases:
        tops = [c.total_score for c in case.candidates if c.valid]
        circs = [
            c.axis_scores.get("circulation", 0.0)
            for c in case.candidates
            if c.valid and c.axis_scores
        ]
        privs = [
            c.axis_scores.get("privacy", 0.0)
            for c in case.candidates
            if c.valid and c.axis_scores
        ]
        d_auto = sum(1 for c in case.candidates if c.auto_grade == "D")
        rows.append(
            [
                case.case_id,
                case.tier,
                f"{case.valid_rate:.3f}",
                str(case.valid_count),
                f"{max(tops) if tops else 0:.1f}",
                f"{_mean(circs):.1f}" if circs else "-",
                f"{_mean(privs):.1f}" if privs else "-",
                str(d_auto),
                f"{case.ab_rate:.3f}" if case.ab_rate is not None else "-",
            ]
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(headers))]
    lines = [
        " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        for row in rows
    ]
    sep = "-+-".join("-" * w for w in widths)
    body = [lines[0], sep, *lines[1:]]
    if report.aggregate:
        body.append("")
        agg = ", ".join(f"{k}={v}" for k, v in sorted(report.aggregate.items()))
        body.append(f"aggregate: {agg}")
    if not report.grades_merged:
        body.append("")
        body.append(
            "(ab_rate pending: run with --merge-grades grades.json after human review)"
        )
    return "\n".join(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PlanSeed Design Benchmark v2 (architect acceptance)"
    )
    parser.add_argument(
        "--cases",
        type=str,
        default="",
        help="comma-separated case ids (e.g. B01,B03)",
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="list Design Benchmark v2 case ids and exit",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=32,
        help="candidate_count (default 32)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON report",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="write JSON report to path",
    )
    parser.add_argument(
        "--export-svg",
        type=str,
        default="",
        metavar="DIR",
        help="export per-candidate SVG under DIR/<case_id>/",
    )
    parser.add_argument(
        "--merge-grades",
        type=str,
        default="",
        metavar="JSON",
        help="merge human grades.json and compute ab_rate",
    )
    parser.add_argument(
        "--grades-only",
        type=str,
        default="",
        metavar="JSON",
        help="merge grades into existing --out report without re-running solver",
    )
    args = parser.parse_args(argv)

    if args.list_cases:
        for cid in list_suite_case_ids():
            case = iter_suite_cases([cid])[0]
            print(f"{cid}\t{case.meta.title}\t{case.meta.tier}")
        return 0

    if args.grades_only:
        if not args.out:
            raise SystemExit("--grades-only requires --out <existing-report.json>")
        with open(args.out, encoding="utf-8") as f:
            data = json.load(f)
        suite = _rehydrate_report(data)
        merge_grades(suite, args.grades_only)
        payload = suite.to_dict()
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(format_acceptance_table(suite))
        return 0

    case_ids = (
        [c.strip() for c in args.cases.split(",") if c.strip()]
        if args.cases
        else None
    )
    export_dir = Path(args.export_svg) if args.export_svg else None
    grades_path = Path(args.merge_grades) if args.merge_grades else None

    report = run_design_suite_acceptance(
        candidate_count=args.count,
        case_ids=case_ids,
        export_svg_dir=export_dir,
        grades_path=grades_path,
    )
    payload = report.to_dict()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"design-benchmark-v2  wave=core  n={report.candidate_count}  "
            f"cases={len(report.cases)}"
        )
        print(format_acceptance_table(report))
    return 0


def _rehydrate_report(data: dict[str, Any]) -> DesignSuiteAcceptanceReport:
    cases: list[DesignCaseAcceptanceReport] = []
    for c in data.get("cases", []):
        candidates = [CandidateAcceptanceRecord(**x) for x in c.get("candidates", [])]
        cases.append(
            DesignCaseAcceptanceReport(
                case_id=c["case_id"],
                case_title=c.get("case_title", ""),
                tier=c.get("tier", "core"),
                focus_metrics=list(c.get("focus_metrics", [])),
                d_grade_hints=list(c.get("d_grade_hints", [])),
                candidate_count=int(c.get("candidate_count", 0)),
                valid_count=int(c.get("valid_count", 0)),
                valid_rate=float(c.get("valid_rate", 0.0)),
                ab_rate=c.get("ab_rate"),
                grade_counts=dict(c.get("grade_counts", {})),
                runtime_s=float(c.get("runtime_s", 0.0)),
                strategy_id=c.get("strategy_id", "guillotine"),
                generator_version=c.get("generator_version", ""),
                candidates=candidates,
            )
        )
    return DesignSuiteAcceptanceReport(
        suite_id=data.get("suite_id", SUITE_ID),
        suite_version=data.get("suite_version", SUITE_VERSION),
        solver_version=data.get("solver_version", SOLVER_VERSION),
        candidate_count=int(data.get("candidate_count", 0)),
        measured_at=data.get("measured_at", ""),
        wave=data.get("wave", "core"),
        cases=cases,
        aggregate=dict(data.get("aggregate", {})),
        grades_merged=bool(data.get("grades_merged", False)),
        notes=list(data.get("notes", [])),
    )


if __name__ == "__main__":
    raise SystemExit(main())

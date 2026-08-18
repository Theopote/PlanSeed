"""Layout generation benchmark — Phase 8.0-C / Suite v1。

比较 LayoutGenerator strategies（默认 Guillotine vs MaxRect）。
指标全部可复现；禁止凭感觉宣称优劣。

单 case 不足以资格判定 MaxRect；请用 ``--suite v1``。
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from packages.schema.identity import SOLVER_VERSION
from packages.schema.program import DesignProgram

from solver.fixtures.benchmark import benchmark_program
from solver.fixtures.layout_suite_v1 import (
    SUITE_ID,
    SUITE_VERSION,
    LayoutSuiteCase,
    iter_suite_cases,
    list_suite_case_ids,
)
from solver.generators.base import LayoutGenerator
from solver.generators.guillotine import GuillotineGenerator
from solver.generators.maxrect import MaxRectGenerator
from solver.pipeline import run_pipeline


@dataclass(frozen=True)
class StrategyMetrics:
    """单策略汇总（越高越好，除非标注）。"""

    strategy_id: str
    generator_version: str
    candidate_count: int
    runtime_s: float
    valid_rate: float
    hard_violation_rate: float
    mean_hard_violations: float
    area_fit: float
    aspect_ratio_quality: float
    mean_aspect_ratio_penalty: float
    circulation: float
    privacy: float
    environment: float
    orientation: float
    mean_repair_count: float
    diversity: float
    distinct_layouts: int
    distinct_valid: int
    top_score: float
    mean_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LayoutGenerationBenchmarkReport:
    case: str
    case_title: str = ""
    base_seed: int = 42
    candidate_count: int = 64
    measured_at: str = ""
    has_locks: bool = False
    strategies: list[StrategyMetrics] = field(default_factory=list)
    pairwise_geometry_diff_rate: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "case_title": self.case_title,
            "base_seed": self.base_seed,
            "candidate_count": self.candidate_count,
            "measured_at": self.measured_at,
            "has_locks": self.has_locks,
            "strategies": [s.to_dict() for s in self.strategies],
            "pairwise_geometry_diff_rate": self.pairwise_geometry_diff_rate,
            "notes": list(self.notes),
        }


@dataclass
class LayoutSuiteBenchmarkReport:
    suite_id: str = SUITE_ID
    suite_version: str = SUITE_VERSION
    solver_version: str = SOLVER_VERSION
    candidate_count: int = 64
    measured_at: str = ""
    cases: list[LayoutGenerationBenchmarkReport] = field(default_factory=list)
    aggregate: dict[str, dict[str, float]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "solver_version": self.solver_version,
            "candidate_count": self.candidate_count,
            "measured_at": self.measured_at,
            "cases": [c.to_dict() for c in self.cases],
            "aggregate": self.aggregate,
            "notes": list(self.notes),
        }


def _geom_fingerprint(candidate: Any) -> str:
    return json.dumps(
        candidate.model_dump(
            exclude={"score", "metrics", "validation", "evaluation", "provenance"}
        ),
        sort_keys=True,
        default=str,
    )


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _aspect_quality(penalty: float) -> float:
    """aspect_ratio_penalty → (0,1]，越高越好。"""
    return 1.0 / (1.0 + max(0.0, penalty))


def summarize_pipeline(
    *,
    strategy_id: str,
    generator_version: str,
    result: Any,
    runtime_s: float,
) -> StrategyMetrics:
    generated = max(1, result.generated)
    hard_rates = []
    hard_counts = []
    area_fits: list[float] = []
    aspects: list[float] = []
    aspect_pens: list[float] = []
    circs: list[float] = []
    privs: list[float] = []
    envs: list[float] = []
    orients: list[float] = []
    repairs: list[float] = []
    scores: list[float] = []

    fps_all: set[str] = set()
    fps_valid: set[str] = set()

    for c in result.all_candidates:
        fp = _geom_fingerprint(c)
        fps_all.add(fp)
        hard_n = 0
        if c.validation is not None:
            hard_n = len(c.validation.hard_violations)
        hard_counts.append(float(hard_n))
        hard_rates.append(1.0 if hard_n > 0 else 0.0)

        if c.validation and c.validation.valid:
            fps_valid.add(fp)
            area_fits.append(float(c.metrics.get("area_accuracy", 0.0)))
            pen = float(c.metrics.get("aspect_ratio_penalty", 0.0))
            aspect_pens.append(pen)
            aspects.append(_aspect_quality(pen))
            repairs.append(float(c.metrics.get("connection_repairs", 0.0) or 0.0))
            if c.evaluation is not None:
                circs.append(float(c.evaluation.circulation_score))
                privs.append(float(c.evaluation.privacy_score))
                envs.append(float(c.evaluation.environment_score))
                orients.append(float(c.evaluation.metrics.orientation_satisfaction))
            else:
                circs.append(float(c.metrics.get("circulation_score", 0.0)))
                privs.append(float(c.metrics.get("privacy_score", 0.0)))
                envs.append(float(c.metrics.get("environment_score", 0.0)))
                orients.append(float(c.metrics.get("orientation_satisfaction", 0.0)))
            if c.score is not None:
                scores.append(float(c.score))

    return StrategyMetrics(
        strategy_id=strategy_id,
        generator_version=generator_version,
        candidate_count=result.generated,
        runtime_s=round(runtime_s, 4),
        valid_rate=round(result.valid / generated, 4),
        hard_violation_rate=round(_mean(hard_rates), 4),
        mean_hard_violations=round(_mean(hard_counts), 4),
        area_fit=round(_mean(area_fits), 4),
        aspect_ratio_quality=round(_mean(aspects), 4),
        mean_aspect_ratio_penalty=round(_mean(aspect_pens), 4),
        circulation=round(_mean(circs), 4),
        privacy=round(_mean(privs), 4),
        environment=round(_mean(envs), 4),
        orientation=round(_mean(orients), 4),
        mean_repair_count=round(_mean(repairs), 4),
        diversity=round(len(fps_all) / generated, 4),
        distinct_layouts=len(fps_all),
        distinct_valid=len(fps_valid),
        top_score=round(max(scores) if scores else 0.0, 2),
        mean_score=round(_mean(scores), 2),
    )


def run_strategy_benchmark(
    generator: LayoutGenerator,
    program: DesignProgram,
    *,
    candidate_count: int | None = None,
    locks: LayoutLocks | None = None,
) -> tuple[StrategyMetrics, Any]:
    prog = program.model_copy(deep=True)
    if candidate_count is not None:
        prog.solver_config = prog.solver_config.model_copy(
            update={"candidate_count": candidate_count}
        )
    t0 = time.perf_counter()
    result = run_pipeline(prog, generator=generator, locks=locks)
    runtime = time.perf_counter() - t0
    version = getattr(generator, "generator_version", "unknown")
    if result.all_candidates and result.all_candidates[0].provenance:
        version = result.all_candidates[0].provenance.generator_version
    metrics = summarize_pipeline(
        strategy_id=generator.strategy_id,
        generator_version=str(version),
        result=result,
        runtime_s=runtime,
    )
    return metrics, result


def pairwise_diff_rate(results: dict[str, Any]) -> dict[str, float]:
    """同 seed 几何不同比例（strategy 两两比较）。"""
    ids = sorted(results.keys())
    out: dict[str, float] = {}
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            ca = results[a].all_candidates
            cb = results[b].all_candidates
            n = min(len(ca), len(cb))
            if n == 0:
                out[f"{a}__vs__{b}"] = 0.0
                continue
            diffs = 0
            for j in range(n):
                if _geom_fingerprint(ca[j]) != _geom_fingerprint(cb[j]):
                    diffs += 1
            out[f"{a}__vs__{b}"] = round(diffs / n, 4)
    return out


_DEFAULT_NOTES = [
    "higher is better except hard_violation_rate / mean_hard_violations / "
    "runtime_s / mean_aspect_ratio_penalty / mean_repair_count",
    "area_fit = mean area_accuracy over valid candidates",
    "aspect_ratio_quality = mean 1/(1+aspect_ratio_penalty) over valid",
    "diversity = distinct geometry fingerprints / generated",
    "MaxRect: implementation=yes; product_qualified=no until Suite v1 gate passes",
]


def run_layout_generation_benchmark(
    *,
    program: DesignProgram | None = None,
    candidate_count: int = 64,
    generators: list[LayoutGenerator] | None = None,
    case: str = "benchmark_11x13_2floors",
    case_title: str = "",
    locks: LayoutLocks | None = None,
) -> LayoutGenerationBenchmarkReport:
    prog = program or benchmark_program()
    gens = generators or [GuillotineGenerator(), MaxRectGenerator()]
    base_seed = prog.solver_config.base_seed

    strategies: list[StrategyMetrics] = []
    by_id: dict[str, Any] = {}
    for gen in gens:
        metrics, result = run_strategy_benchmark(
            gen, prog, candidate_count=candidate_count, locks=locks
        )
        strategies.append(metrics)
        by_id[gen.strategy_id] = result

    return LayoutGenerationBenchmarkReport(
        case=case,
        case_title=case_title,
        base_seed=base_seed,
        candidate_count=candidate_count,
        measured_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        has_locks=bool(
            locks is not None
            and (locks.rooms or locks.zones or locks.stair is not None)
        ),
        strategies=strategies,
        pairwise_geometry_diff_rate=pairwise_diff_rate(by_id),
        notes=list(_DEFAULT_NOTES),
    )


def run_suite_case_benchmark(
    suite_case: LayoutSuiteCase,
    *,
    candidate_count: int = 64,
    generators: list[LayoutGenerator] | None = None,
) -> LayoutGenerationBenchmarkReport:
    return run_layout_generation_benchmark(
        program=suite_case.program,
        candidate_count=candidate_count,
        generators=generators,
        case=suite_case.meta.id,
        case_title=suite_case.meta.title,
        locks=suite_case.locks,
    )


def _aggregate_strategies(
    cases: list[LayoutGenerationBenchmarkReport],
) -> dict[str, dict[str, float]]:
    """跨 case 对同 strategy 做简单均值（资格总览用，非加权）。"""
    buckets: dict[str, dict[str, list[float]]] = {}
    numeric_keys = [
        "valid_rate",
        "area_fit",
        "aspect_ratio_quality",
        "mean_aspect_ratio_penalty",
        "circulation",
        "privacy",
        "environment",
        "orientation",
        "mean_repair_count",
        "diversity",
        "top_score",
        "mean_score",
        "runtime_s",
    ]
    for case in cases:
        for s in case.strategies:
            bucket = buckets.setdefault(s.strategy_id, {k: [] for k in numeric_keys})
            data = s.to_dict()
            for k in numeric_keys:
                bucket[k].append(float(data[k]))
    return {
        sid: {k: round(_mean(vs), 4) for k, vs in vals.items()}
        for sid, vals in buckets.items()
    }


def run_layout_suite_benchmark(
    *,
    candidate_count: int = 64,
    case_ids: list[str] | None = None,
    generators: list[LayoutGenerator] | None = None,
) -> LayoutSuiteBenchmarkReport:
    cases = iter_suite_cases(case_ids)
    reports: list[LayoutGenerationBenchmarkReport] = []
    for sc in cases:
        reports.append(
            run_suite_case_benchmark(
                sc, candidate_count=candidate_count, generators=generators
            )
        )
    return LayoutSuiteBenchmarkReport(
        suite_id=SUITE_ID,
        suite_version=SUITE_VERSION,
        candidate_count=candidate_count,
        measured_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        cases=reports,
        aggregate=_aggregate_strategies(reports),
        notes=[
            *_DEFAULT_NOTES,
            "Suite v1 is the minimum gate for MaxRect Alpha candidate-pool entry",
            "aggregate = unweighted mean of per-case strategy metrics",
        ],
    )


def format_report_table(report: LayoutGenerationBenchmarkReport) -> str:
    headers = [
        "strategy",
        "valid",
        "area",
        "asp_pen",
        "circ",
        "priv",
        "env",
        "repair",
        "div",
        "top",
        "t_s",
    ]
    rows: list[list[str]] = [headers]
    for s in report.strategies:
        rows.append(
            [
                s.strategy_id,
                f"{s.valid_rate:.3f}",
                f"{s.area_fit:.3f}",
                f"{s.mean_aspect_ratio_penalty:.1f}",
                f"{s.circulation:.1f}",
                f"{s.privacy:.1f}",
                f"{s.environment:.1f}",
                f"{s.mean_repair_count:.2f}",
                f"{s.diversity:.3f}",
                f"{s.top_score:.1f}",
                f"{s.runtime_s:.3f}",
            ]
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(headers))]
    lines = [
        " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        for row in rows
    ]
    sep = "-+-".join("-" * w for w in widths)
    body = [lines[0], sep, *lines[1:]]
    if report.pairwise_geometry_diff_rate:
        body.append("")
        body.append("pairwise geometry diff rate (same seed):")
        for k, v in sorted(report.pairwise_geometry_diff_rate.items()):
            body.append(f"  {k}: {v:.3f}")
    return "\n".join(body)


def format_suite_table(report: LayoutSuiteBenchmarkReport) -> str:
    lines: list[str] = []
    for case in report.cases:
        title = f"{case.case}  {case.case_title}".strip()
        lines.append(f"=== {title}  n={case.candidate_count} ===")
        lines.append(format_report_table(case))
        lines.append("")
    if report.aggregate:
        lines.append("=== aggregate (unweighted mean) ===")
        headers = [
            "strategy",
            "valid",
            "area",
            "asp_pen",
            "circ",
            "priv",
            "env",
            "repair",
            "top",
            "mean",
        ]
        rows: list[list[str]] = [headers]
        for sid, vals in sorted(report.aggregate.items()):
            rows.append(
                [
                    sid,
                    f"{vals['valid_rate']:.3f}",
                    f"{vals['area_fit']:.3f}",
                    f"{vals['mean_aspect_ratio_penalty']:.1f}",
                    f"{vals['circulation']:.1f}",
                    f"{vals['privacy']:.1f}",
                    f"{vals['environment']:.1f}",
                    f"{vals['mean_repair_count']:.2f}",
                    f"{vals['top_score']:.1f}",
                    f"{vals['mean_score']:.1f}",
                ]
            )
        widths = [max(len(r[i]) for r in rows) for i in range(len(headers))]
        lines.append(
            " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(rows[0]))
        )
        lines.append("-+-".join("-" * w for w in widths))
        for row in rows[1:]:
            lines.append(
                " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PlanSeed layout-generation-benchmark (Guillotine vs MaxRect)"
    )
    parser.add_argument(
        "--suite",
        type=str,
        default="",
        help="run suite (v1) instead of legacy single case",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default="",
        help="comma-separated suite case ids (e.g. B01,B03,B11)",
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="list Layout Suite v1 case ids and exit",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=64,
        help="candidate_count per strategy (default 64)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON report instead of table",
    )
    parser.add_argument(
        "--qualify",
        action="store_true",
        help="with --suite v1: run MaxRect qualification gate on report",
    )
    parser.add_argument(
        "--qualify-only",
        type=str,
        default="",
        metavar="JSON",
        help="evaluate gate from existing suite JSON (no re-run)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="optional path to write JSON report",
    )
    args = parser.parse_args(argv)

    if args.qualify_only:
        from solver.benchmark.maxrect_qualification import (
            evaluate_maxrect_qualification,
            format_qualification_report,
        )
        with open(args.qualify_only, encoding="utf-8") as f:
            data = json.load(f)
        suite = LayoutSuiteBenchmarkReport(
            suite_id=data.get("suite_id", SUITE_ID),
            suite_version=data.get("suite_version", SUITE_VERSION),
            candidate_count=int(data.get("candidate_count", 0)),
            measured_at=data.get("measured_at", ""),
            cases=[
                LayoutGenerationBenchmarkReport(
                    case=c["case"],
                    case_title=c.get("case_title", ""),
                    base_seed=int(c.get("base_seed", 42)),
                    candidate_count=int(c.get("candidate_count", 0)),
                    measured_at=c.get("measured_at", ""),
                    has_locks=bool(c.get("has_locks", False)),
                    strategies=[],  # not needed for qualify-only path
                    pairwise_geometry_diff_rate=c.get("pairwise_geometry_diff_rate", {}),
                    notes=list(c.get("notes", [])),
                )
                for c in data.get("cases", [])
            ],
            aggregate=data.get("aggregate", {}),
            notes=list(data.get("notes", [])),
        )
        # Rehydrate strategy metrics for gate
        for i, cdata in enumerate(data.get("cases", [])):
            from solver.benchmark.layout_generation import StrategyMetrics

            suite.cases[i].strategies = [
                StrategyMetrics(**s) for s in cdata.get("strategies", [])
            ]
        qual = evaluate_maxrect_qualification(suite)
        if args.json:
            print(json.dumps(qual.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(format_qualification_report(qual))
        return 0 if qual.passed else 1

    if args.list_cases:
        for cid in list_suite_case_ids():
            print(cid)
        return 0

    case_ids = (
        [c.strip() for c in args.cases.split(",") if c.strip()]
        if args.cases
        else None
    )

    if args.suite:
        if args.suite.lower() not in ("v1", "layout-v1", SUITE_ID, "1"):
            raise SystemExit(f"unknown suite {args.suite!r}; use v1")
        report = run_layout_suite_benchmark(
            candidate_count=args.count, case_ids=case_ids
        )
        payload = report.to_dict()
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
        qual = None
        if args.qualify:
            from solver.benchmark.maxrect_qualification import (
                evaluate_maxrect_qualification,
                format_qualification_report,
            )
            qual = evaluate_maxrect_qualification(report)
            if args.out:
                qual_path = args.out.replace(".json", "_qualification.json")
                if qual_path == args.out:
                    qual_path = args.out + ".qualification.json"
                with open(qual_path, "w", encoding="utf-8") as f:
                    json.dump(qual.to_dict(), f, ensure_ascii=False, indent=2)
                    f.write("\n")
        if args.json:
            out = payload
            if qual is not None:
                out = {**payload, "qualification": qual.to_dict()}
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(
                f"layout-benchmark-suite  id={report.suite_id}  "
                f"version={report.suite_version}  n={report.candidate_count}  "
                f"cases={len(report.cases)}"
            )
            print(format_suite_table(report))
            if qual is not None:
                print()
                print(format_qualification_report(qual))
        if qual is not None and not qual.passed:
            return 1
        return 0

    # legacy single-case (B03-equivalent) for back-compat
    report = run_layout_generation_benchmark(candidate_count=args.count)
    payload = report.to_dict()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"layout-generation-benchmark  case={report.case}  "
            f"base_seed={report.base_seed}  n={report.candidate_count}"
        )
        print(format_report_table(report))
        print(
            "\n(hint: use --suite v1 for Layout Benchmark Suite; "
            "single case is not a MaxRect qualification gate)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

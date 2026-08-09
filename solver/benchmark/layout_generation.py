"""Layout generation benchmark — Phase 8.0-C。

比较 LayoutGenerator strategies（默认 Guillotine vs MaxRect）。
指标全部可复现；禁止凭感觉宣称优劣。
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from packages.schema.program import DesignProgram

from solver.fixtures.benchmark import benchmark_program
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
    orientation: float
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
    base_seed: int
    candidate_count: int
    measured_at: str = ""
    strategies: list[StrategyMetrics] = field(default_factory=list)
    pairwise_geometry_diff_rate: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "base_seed": self.base_seed,
            "candidate_count": self.candidate_count,
            "measured_at": self.measured_at,
            "strategies": [s.to_dict() for s in self.strategies],
            "pairwise_geometry_diff_rate": self.pairwise_geometry_diff_rate,
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
    orients: list[float] = []
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
            if c.evaluation is not None:
                circs.append(float(c.evaluation.circulation_score))
                orients.append(float(c.evaluation.metrics.orientation_satisfaction))
            else:
                circs.append(float(c.metrics.get("circulation_score", 0.0)))
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
        orientation=round(_mean(orients), 4),
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
) -> tuple[StrategyMetrics, Any]:
    prog = program.model_copy(deep=True)
    if candidate_count is not None:
        prog.solver_config = prog.solver_config.model_copy(
            update={"candidate_count": candidate_count}
        )
    t0 = time.perf_counter()
    result = run_pipeline(prog, generator=generator)
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


def run_layout_generation_benchmark(
    *,
    program: DesignProgram | None = None,
    candidate_count: int = 32,
    generators: list[LayoutGenerator] | None = None,
    case: str = "benchmark_11x13_2floors",
) -> LayoutGenerationBenchmarkReport:
    prog = program or benchmark_program()
    gens = generators or [GuillotineGenerator(), MaxRectGenerator()]
    base_seed = prog.solver_config.base_seed

    strategies: list[StrategyMetrics] = []
    by_id: dict[str, Any] = {}
    for gen in gens:
        metrics, result = run_strategy_benchmark(
            gen, prog, candidate_count=candidate_count
        )
        strategies.append(metrics)
        by_id[gen.strategy_id] = result

    report = LayoutGenerationBenchmarkReport(
        case=case,
        base_seed=base_seed,
        candidate_count=candidate_count,
        measured_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        strategies=strategies,
        pairwise_geometry_diff_rate=pairwise_diff_rate(by_id),
        notes=[
            "higher is better except hard_violation_rate / mean_hard_violations / runtime_s / mean_aspect_ratio_penalty",
            "area_fit = mean area_accuracy over valid candidates",
            "aspect_ratio_quality = mean 1/(1+aspect_ratio_penalty) over valid",
            "diversity = distinct geometry fingerprints / generated",
        ],
    )
    return report


def format_report_table(report: LayoutGenerationBenchmarkReport) -> str:
    headers = [
        "strategy",
        "valid",
        "hard_v",
        "area",
        "asp_pen",
        "circ",
        "orient",
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
                f"{s.hard_violation_rate:.3f}",
                f"{s.area_fit:.3f}",
                f"{s.mean_aspect_ratio_penalty:.1f}",
                f"{s.circulation:.2f}",
                f"{s.orientation:.3f}",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PlanSeed layout-generation-benchmark (Guillotine vs MaxRect)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=32,
        help="candidate_count per strategy (default 32)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON report instead of table",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="optional path to write JSON report",
    )
    args = parser.parse_args(argv)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

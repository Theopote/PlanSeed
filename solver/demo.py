"""CLI demo — 快速验证 solver pipeline。"""

from __future__ import annotations

import json

from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline


def build_benchmark_program():
    return benchmark_program()


def main() -> None:
    program = build_benchmark_program()
    result = run_pipeline(program)
    m = result.compute_metrics()

    print(f"Generated candidates: {result.generated}")
    print(f"Valid candidates: {result.valid}")
    print(f"Rejected candidates: {result.rejected}")
    print(f"valid_ratio: {m.valid_ratio:.3f}")
    print(f"distinct_layouts: {m.distinct_layout_count}")
    print(f"average_score: {m.average_score:.2f}")
    print(f"top_score: {m.top_score:.2f}")
    print(f"average_soft_violations: {m.average_soft_violation_count:.2f}")
    print()

    if result.violation_summary:
        print("Hard violations (aggregate):")
        for key, count in sorted(result.violation_summary.items()):
            print(f"  {key}: {count}")
        print()

    print("Top candidates:")
    for i, c in enumerate(result.top_candidates, 1):
        valid = c.validation.valid if c.validation else False
        print(f"#{i} seed={c.seed:02d} score={c.score:.1f} valid={valid}")
        metrics = {
            k: c.metrics[k]
            for k in (
                "compactness",
                "area_accuracy",
                "preferred_adjacency_satisfaction",
                "stair_alignment",
                "wet_zone_alignment",
            )
            if k in c.metrics
        }
        if metrics:
            print(f"    metrics: {json.dumps(metrics, ensure_ascii=False)}")
    print()


if __name__ == "__main__":
    main()

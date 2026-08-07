"""CLI demo — 快速验证 solver pipeline。"""

from __future__ import annotations

import json

from packages.schema.requirements import RequirementSpec, SiteRequirements
from solver.pipeline import run_pipeline
from solver.program.requirements_normalize import normalize_requirements


def build_benchmark_program():
    req = RequirementSpec(
        site=SiteRequirements(width=11, depth=13),
        floor_count=2,
    )
    return normalize_requirements(req)


def main() -> None:
    program = build_benchmark_program()
    result = run_pipeline(program)

    print(f"Generated candidates: {result.generated}")
    print(f"Valid candidates: {result.valid}")
    print(f"Rejected candidates: {result.rejected}")
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

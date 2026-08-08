"""
CLI：生成 Top 候选的 SVG 调试图。

用法：
  uv run python -m solver.visualize
  uv run python -m solver.visualize --out debug --top 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline
from solver.visualize.svg import write_candidate_svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PlanSeed SVG debug 导出")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("debug"),
        help="输出目录（默认 debug/）",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="导出 Top-K 候选（默认 5）",
    )
    args = parser.parse_args(argv)

    program = benchmark_program()
    result = run_pipeline(program)

    labels = {fl.id: fl.label or fl.id for fl in program.floors}
    targets = {r.id: r.target_area for r in program.rooms}
    w = program.buildable.width
    d = program.buildable.depth

    written: list[Path] = []
    for i, candidate in enumerate(result.top_candidates[: args.top], start=1):
        path = args.out / f"candidate_{i:02d}_seed{candidate.seed:02d}.svg"
        write_candidate_svg(
            candidate,
            path,
            floor_width=w,
            floor_depth=d,
            floor_labels=labels,
            target_areas=targets,
            site=program.site,
        )
        written.append(path)

    m = result.compute_metrics()
    print(f"Generated: {result.generated}  Valid: {result.valid}  distinct={m.distinct_layout_count}")
    print(f"Wrote {len(written)} SVG(s) → {args.out.resolve()}")
    for p in written:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

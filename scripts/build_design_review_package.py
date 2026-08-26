"""从 benchmark report 生成建筑师评审包（REVIEW.md + grades-template.json）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_review_package(report_path: Path, out_dir: Path) -> None:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)

    grades: dict = {
        "suite": "design-benchmark-v2",
        "suite_version": "v2",
        "candidate_count": data.get("candidate_count", 32),
        "reviewer": "",
        "reviewed_at": "",
        "grades": {},
    }
    lines = [
        "# Design Benchmark v2 — 建筑师评审包",
        "",
        f"来源报告：`{report_path.name}`",
        "",
        "## 评级标准",
        "",
        "| Grade | 含义 |",
        "|-------|------|",
        "| A | 基本可以继续深化 |",
        "| B | 可以修改后继续 |",
        "| C | 只能作为构思参考 |",
        "| D | 明显不可用（invalid 已自动 D）|",
        "",
    ]

    for case in data["cases"]:
        cid = case["case_id"]
        grades["grades"][cid] = {}
        lines.extend(
            [
                f"## {cid} — {case['case_title']}",
                "",
                f"- valid: **{case['valid_count']}/32**",
                f"- D 级特征: {', '.join(case['d_grade_hints'])}",
                "",
                "| index | seed | valid | score | SVG | 评级 |",
                "|-------|------|-------|-------|-----|------|",
            ]
        )
        for c in case["candidates"]:
            svg = f"{cid}/candidate_{c['index']:03d}.svg"
            if c["valid"]:
                lines.append(
                    f"| {c['index']} | {c['seed']} | yes | {c['total_score']} "
                    f"| [{svg}]({svg}) | 待填 |"
                )
                grades["grades"][cid][str(c["index"])] = {
                    "grade": "",
                    "notes": "",
                    "svg": svg,
                }
            else:
                lines.append(
                    f"| {c['index']} | {c['seed']} | no | — | [{svg}]({svg}) | 自动 D |"
                )
        lines.append("")

    lines.extend(
        [
            "## 提交评级",
            "",
            "1. 打开各 case 目录下的 SVG 查看平面",
            "2. 在 `grades-template.json` 填写 valid candidate 的 `grade`（A/B/C/D）",
            "3. 运行：",
            "",
            "```bash",
            "uv run python -m solver.benchmark --suite design-v2 \\",
            f"  --merge-grades {out_dir.as_posix()}/grades-template.json \\",
            f"  --grades-only {out_dir.as_posix()}/grades-template.json \\",
            f"  --out {report_path.as_posix()}",
            "```",
            "",
        ]
    )

    (out_dir / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "grades-template.json").write_text(
        json.dumps(grades, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Design Benchmark v2 评审包")
    parser.add_argument("report", type=Path, help="benchmark report JSON")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录（默认与 report 同目录）",
    )
    args = parser.parse_args()
    out_dir = args.out_dir or args.report.parent
    build_review_package(args.report, out_dir)
    print(f"Wrote {out_dir / 'REVIEW.md'}")
    print(f"Wrote {out_dir / 'grades-template.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

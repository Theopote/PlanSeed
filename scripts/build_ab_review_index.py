"""从 design-benchmark 自动报告生成人工 ab_rate 审阅索引（仅 valid 候选）。

用法：
  uv run python scripts/build_ab_review_index.py \\
    --report debug/design-benchmark-v2/auto_rerun_for_ab.json \\
    --svg-root debug/design-benchmark-v2/review-ab-rerate \\
    --out-dir debug/design-benchmark-v2/review-ab-rerate
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _axis(c: dict) -> str:
    a = c.get("axis_scores") or {}
    parts = []
    for k in ("circulation", "privacy", "environment", "spatial", "program"):
        if k in a:
            parts.append(f"{k[:4]}={float(a[k]):.0f}")
    return " ".join(parts)


def build(report: dict, svg_root: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    grades_seed: dict[str, dict] = {}
    rows_html: list[str] = []

    for case in report.get("cases") or []:
        cid = case["case_id"]
        grades_seed[cid] = {}
        valids = [c for c in case.get("candidates") or [] if c.get("valid")]
        valids.sort(key=lambda c: float(c.get("total_score") or 0), reverse=True)
        rows_html.append(
            f"<h2>{html.escape(cid)} — {html.escape(case.get('case_title') or '')} "
            f"<small>valid {case.get('valid_count')}/{case.get('candidate_count')} "
            f"= {case.get('valid_rate')}</small></h2>"
        )
        rows_html.append("<table><thead><tr>"
                         "<th>#</th><th>seed</th><th>score</th><th>axes</th>"
                         "<th>gate/priv</th><th>svg</th><th>grade</th><th>notes</th>"
                         "</tr></thead><tbody>")
        for c in valids:
            idx = int(c["index"])
            grades_seed[cid][str(idx)] = {
                "grade": "",
                "notes": "",
                "svg": f"{cid}/candidate_{idx:03d}.svg",
            }
            mp = c.get("metrics_proxy") or {}
            gate = mp.get("architectural_gate_pass", "")
            priv = mp.get("private_through_count", "")
            svg_rel = f"{cid}/candidate_{idx:03d}.svg"
            svg_path = svg_root / svg_rel
            link = (
                f'<a href="{html.escape(svg_rel)}" target="_blank">open</a>'
                if svg_path.exists()
                else f'<span class="missing">{html.escape(svg_rel)}</span>'
            )
            rows_html.append(
                "<tr>"
                f"<td>{idx:03d}</td>"
                f"<td>{c.get('seed')}</td>"
                f"<td>{float(c.get('total_score') or 0):.1f}</td>"
                f"<td><code>{html.escape(_axis(c))}</code></td>"
                f"<td>gate={gate} priv={priv}</td>"
                f"<td>{link}</td>"
                f"<td contenteditable=\"true\" data-case=\"{cid}\" data-idx=\"{idx}\" "
                f"class=\"grade-cell\"></td>"
                f"<td contenteditable=\"true\" class=\"notes-cell\"></td>"
                "</tr>"
            )
        rows_html.append("</tbody></table>")

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>Design Benchmark ab_rate 审阅</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 1.5rem; background: #f6f3ee; color: #1a1a1a; }}
h1 {{ font-size: 1.25rem; }}
h2 {{ margin-top: 2rem; font-size: 1.05rem; border-bottom: 1px solid #ccc; padding-bottom: .3rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: .85rem; background: #fff; }}
th, td {{ border: 1px solid #ddd; padding: .35rem .5rem; vertical-align: top; }}
th {{ background: #e8e2d8; text-align: left; }}
code {{ font-size: .78rem; }}
.missing {{ color: #a33; }}
.grade-cell {{ min-width: 2.5rem; background: #fffbe6; }}
.notes-cell {{ min-width: 12rem; background: #fffbe6; }}
.hint {{ color: #555; max-width: 52rem; }}
</style>
</head>
<body>
<h1>Design Benchmark v2 — 人工 ab_rate 审阅索引</h1>
<p class="hint">仅列出 <b>valid</b> 候选（按总分降序）。在 grade 列填 A/B/C/D，notes 写评语；
完成后把结果抄入同目录 <code>grades-template.json</code>（或导出下方 JSON）。
旧 grades 不可套用到本轮几何。</p>
<p class="hint">协议见 <code>docs/design-benchmark-v2.md</code>。
A=可直接用 · B=改后可继续 · C=结构问题大 · D=不可用（含 invalid，已排除）。</p>
{"".join(rows_html)}
<script>
function exportGrades() {{
  const out = {{ B01: {{}}, B04: {{}}, B06: {{}}, B12: {{}} }};
  document.querySelectorAll('.grade-cell').forEach(td => {{
    const g = (td.textContent || '').trim().toUpperCase();
    if (!g) return;
    const caseId = td.dataset.case;
    const idx = td.dataset.idx;
    const notesTd = td.parentElement.querySelector('.notes-cell');
    out[caseId][idx] = {{
      grade: g,
      notes: (notesTd && notesTd.textContent || '').trim(),
      svg: caseId + '/candidate_' + String(idx).padStart(3,'0') + '.svg'
    }};
  }});
  const blob = new Blob([JSON.stringify({{ grades: out }}, null, 2)], {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'grades-from-review.json';
  a.click();
}}
</script>
<p><button type="button" onclick="exportGrades()">导出本页评级 JSON</button></p>
</body>
</html>
"""
    (out_dir / "index.html").write_text(page, encoding="utf-8")

    template = {
        "suite": "design-benchmark-v2",
        "suite_version": report.get("suite_version", "v2"),
        "candidate_count": report.get("candidate_count", 32),
        "reviewer": "",
        "reviewed_at": "",
        "source_report": str(Path("debug/design-benchmark-v2/auto_rerun_for_ab.json")),
        "svg_root": str(svg_root),
        "notes": "仅预填 valid 候选 index；填 grade/notes 后用 --grades-only 合并。",
        "grades": grades_seed,
    }
    (out_dir / "grades-template.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_dir / 'index.html'}")
    print(f"wrote {out_dir / 'grades-template.json'}")
    for cid, slots in grades_seed.items():
        print(f"  {cid}: {len(slots)} valid slots")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--svg-root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    build(report, args.svg_root, args.out_dir)


if __name__ == "__main__":
    main()

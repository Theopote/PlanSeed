"""生成 Phase 7.1 Print smoke 压力 HTML（供 Desktop / Edge Print to PDF）。

用法:
  uv run python scripts/generate_print_smoke_reports.py

输出: debug/print-smoke/*.html + index.html

说明: 本脚本只产出 HTML fixture，不代替 WebView2 真实打印验收。
详见 docs/phase-7.1-print-smoke.md
"""

from __future__ import annotations

from pathlib import Path

from backend.services.report_builder import build_design_report
from backend.services.report_html import render_report_html
from packages.schema.scoring import DesignFinding, DesignScore, FindingSeverity

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "debug" / "print-smoke"


def _svg(w: int = 220, h: int = 180, label: str = "F") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'<rect x="8" y="8" width="{w - 16}" height="{h - 16}" '
        f'fill="#f3f0e8" stroke="#333" stroke-width="2"/>'
        f'<text x="{w // 2}" y="{h // 2}" text-anchor="middle" '
        f'font-size="18" fill="#333">{label}</text>'
        f"</svg>"
    )


def _score(*, n_findings: int = 4) -> DesignScore:
    findings: list[DesignFinding] = []
    sevs = [
        FindingSeverity.POSITIVE,
        FindingSeverity.WARNING,
        FindingSeverity.PROBLEM,
        FindingSeverity.INFO,
    ]
    titles = ["比例良好", "流线偏长", "私密不足", "朝向可改善", "湿区对齐", "进深偏大"]
    for i in range(n_findings):
        findings.append(
            DesignFinding(
                id=f"f.{i}",
                category=["spatial", "circulation", "privacy", "environment"][i % 4],
                severity=sevs[i % 4],
                title=titles[i % len(titles)] + f" #{i + 1}",
                message=f"压力 Finding 文案 {i + 1}：" + ("详细说明。" * (1 + i % 3)),
                room_ids=[f"r{(i % 8) + 1}"] if i % 2 == 0 else [],
            )
        )
    return DesignScore(
        program_score=80,
        spatial_score=78,
        circulation_score=75,
        privacy_score=72,
        environment_score=70,
        technical_score=76,
        robustness_score=74,
        total_score=75.0,
        findings=findings,
    )


def _placements(floor_ids: list[str], rooms_per_floor: int) -> list[dict]:
    out: list[dict] = []
    n = 0
    for fid in floor_ids:
        for j in range(rooms_per_floor):
            n += 1
            out.append(
                {
                    "room_id": f"r{n}",
                    "floor_id": fid,
                    "x": float((j % 4) * 3),
                    "y": float((j // 4) * 3),
                    "width": 3.0,
                    "depth": 3.2,
                    "area": 9.6,
                }
            )
    return out


def _program_from_placements(placements: list[dict]) -> dict:
    rooms = []
    for p in placements:
        rooms.append(
            {
                "id": p["room_id"],
                "name": f"房间{p['room_id'][1:]}",
                "category": "living",
                "target_area": 10.0,
                "floor_id": p["floor_id"],
            }
        )
    return {"rooms": rooms}


def _req(
    *,
    floor_count: int,
    assumptions: list[dict] | None = None,
    unknowns: list[dict] | None = None,
    north_angle: float | None = 0.0,
) -> dict:
    site: dict = {"width": 11, "depth": 13}
    if north_angle is not None:
        site["north_angle"] = north_angle
    return {
        "floor_count": floor_count,
        "household": {"bedrooms": 3, "bathrooms": 2, "has_garage": True},
        "site": site,
        "preferences": {"prefer_south_facing_living": True},
        "assumptions": assumptions
        if assumptions is not None
        else [
            {
                "key": "site.setbacks",
                "value": 0,
                "reason": "未提供退界，按 0 处理",
                "source": "implicit",
            }
        ],
        "unknowns": unknowns
        if unknowns is not None
        else [{"key": "site.entrance_edge", "description": "入口朝向未定"}],
        "spaces": [],
    }


def _candidate(
    *,
    floor_ids: list[str],
    rooms_per_floor: int = 4,
    n_findings: int = 4,
    north_in_svg_label: bool = True,
) -> dict:
    placements = _placements(floor_ids, rooms_per_floor)
    floor_svgs = {
        fid: _svg(label=fid if north_in_svg_label else "?") for fid in floor_ids
    }
    return {
        "id": "c-smoke",
        "seed": 42,
        "score": 75.0,
        "label": "A",
        "svg": _svg(label="+".join(floor_ids)),
        "floor_svgs": floor_svgs,
        "design_score": _score(n_findings=n_findings).model_dump(mode="json"),
        "provenance": {
            "solver_version": "smoke-s",
            "generator_version": "smoke-g",
            "evaluation_version": "smoke-e",
        },
        "revision_status": "generated",
        "revision_id": "c-smoke:gen:1",
        "placements": placements,
        "validation": {"valid": True, "hard_violations": [], "soft_violations": []},
    }


def _write(case_id: str, title: str, html: str, index_rows: list[tuple[str, str, str]]) -> None:
    path = OUT / f"{case_id}.html"
    path.write_text(html, encoding="utf-8")
    index_rows.append((case_id, title, path.name))
    print(f"  wrote {path.relative_to(ROOT)}")


def _build(
    *,
    project_name: str,
    floor_ids: list[str],
    locale: str,
    rooms_per_floor: int = 4,
    n_findings: int = 4,
    assumptions: list[dict] | None = None,
    unknowns: list[dict] | None = None,
    north_angle: float | None = 0.0,
) -> str:
    cand = _candidate(
        floor_ids=floor_ids,
        rooms_per_floor=rooms_per_floor,
        n_findings=n_findings,
    )
    report = build_design_report(
        project_name=project_name,
        requirement_spec=_req(
            floor_count=len(floor_ids),
            assumptions=assumptions,
            unknowns=unknowns,
            north_angle=north_angle,
        ),
        program=_program_from_placements(cand["placements"]),
        candidate=cand,
        export_mode="preview",
        locale=locale,
    )
    return render_report_html(report)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str, str]] = []
    print(f"Generating → {OUT}")

    cases: list[tuple[str, str, dict]] = [
        ("01_floors_1f", "F1 · 1 层", {"floor_ids": ["F1"], "project_name": "单层烟测"}),
        ("02_floors_2f", "F2 · 2 层", {"floor_ids": ["F1", "F2"], "project_name": "两层烟测"}),
        (
            "03_floors_3f",
            "F3 · 3 层",
            {"floor_ids": ["F1", "F2", "F3"], "project_name": "三层烟测"},
        ),
        ("04_name_short", "N1 · 短项目名", {"floor_ids": ["F1", "F2"], "project_name": "短名"}),
        (
            "05_name_long_zh",
            "N2 · 超长中文项目名",
            {
                "floor_ids": ["F1", "F2"],
                "project_name": (
                    "江南水乡庭院式独栋住宅方案深化设计与业主沟通归档稿"
                    "——含南北向场地约束与多代同堂功能分区说明"
                ),
            },
        ),
        (
            "06_many_rooms",
            "R1 · 大量房间",
            {
                "floor_ids": ["F1", "F2"],
                "rooms_per_floor": 14,
                "project_name": "多房间面积表压力",
            },
        ),
        (
            "07_many_findings",
            "K1 · 大量 Findings",
            {
                "floor_ids": ["F1", "F2"],
                "n_findings": 24,
                "project_name": "Findings 压力",
            },
        ),
        (
            "08_no_assumptions",
            "A0 · 无 Assumption",
            {
                "floor_ids": ["F1", "F2"],
                "assumptions": [],
                "project_name": "无假设",
            },
        ),
        (
            "09_many_unknowns",
            "U1 · 大量 Unknown",
            {
                "floor_ids": ["F1", "F2"],
                "unknowns": [
                    {
                        "key": f"u.{i}",
                        "description": f"未决事项 {i + 1}：场地/入口/层高/退界细节待业主确认",
                        "priority": "normal",
                    }
                    for i in range(18)
                ],
                "project_name": "多 Unknown",
            },
        ),
        (
            "10_blocking_unknown",
            "U2 · blocking Unknown",
            {
                "floor_ids": ["F1", "F2"],
                "unknowns": [
                    {
                        "key": "site.boundary",
                        "description": "用地红线未提供，无法确认可建范围",
                        "priority": "blocking",
                    },
                    {
                        "key": "site.entrance_edge",
                        "description": "主入口朝向未定",
                        "priority": "normal",
                    },
                ],
                "project_name": "Blocking Unknown",
            },
        ),
        (
            "11_locale_en",
            "L-en · English locale",
            {
                "floor_ids": ["F1", "F2"],
                "locale": "en",
                "project_name": "Print Smoke EN",
                "north_angle": 45.0,
            },
        ),
        (
            "12_locale_zh",
            "L-zh · 中文 locale",
            {
                "floor_ids": ["F1", "F2"],
                "locale": "zh-CN",
                "project_name": "打印烟测中文",
                "north_angle": 30.0,
            },
        ),
    ]

    for case_id, title, kwargs in cases:
        floor_ids = kwargs.pop("floor_ids")
        locale = kwargs.pop("locale", "zh-CN")
        html = _build(floor_ids=floor_ids, locale=locale, **kwargs)
        _write(case_id, title, html, rows)

    # 北向未定义对照（额外）
    html_no_north = _build(
        project_name="北向未定义",
        floor_ids=["F1", "F2"],
        locale="zh-CN",
        north_angle=None,
    )
    _write("13_north_undefined", "北向未定义（不画假 ↑N）", html_no_north, rows)

    index = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'/>",
        "<title>PlanSeed 7.1 Print Smoke</title>",
        "<style>body{font:14px/1.5 system-ui,sans-serif;max-width:40rem;",
        "margin:2rem auto;padding:0 1rem} li{margin:.35rem 0}</style></head><body>",
        "<h1>Phase 7.1 Print Smoke</h1>",
        "<p>打开下方 HTML → Print → Microsoft Print to PDF。"
        "关门验收以 <strong>Desktop WebView2</strong> 为准。"
        "清单见 <code>docs/phase-7.1-print-smoke.md</code>。</p>",
        "<ol>",
    ]
    for case_id, title, name in rows:
        index.append(f'<li><a href="{name}">{case_id}</a> — {title}</li>')
    index.extend(["</ol></body></html>"])
    (OUT / "index.html").write_text("\n".join(index), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT) / 'index.html'}")
    print("done.")


if __name__ == "__main__":
    main()

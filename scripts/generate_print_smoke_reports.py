"""生成 Phase 7.1.1-C 打印样本 HTML（P01–P08）。

用法:
  uv run python scripts/generate_print_smoke_reports.py

输出: debug/print-smoke/P0x_*.html + index.html

仅供手测对照；不代替 Windows Tauri + WebView2 + Microsoft Print to PDF。
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


def _score(*, n_findings: int = 4, locale_en: bool = False) -> DesignScore:
    findings: list[DesignFinding] = []
    sevs = [
        FindingSeverity.POSITIVE,
        FindingSeverity.WARNING,
        FindingSeverity.PROBLEM,
        FindingSeverity.INFO,
    ]
    if locale_en:
        titles = [
            "Good proportions",
            "Long circulation",
            "Privacy concern",
            "Orientation",
            "Wet stack",
            "Deep room",
        ]
        msg = "Finding detail "
        detail = "More explanation. "
    else:
        titles = ["比例良好", "流线偏长", "私密不足", "朝向可改善", "湿区对齐", "进深偏大"]
        msg = "压力 Finding 文案 "
        detail = "详细说明。"
    for i in range(n_findings):
        findings.append(
            DesignFinding(
                id=f"f.{i}",
                category=["spatial", "circulation", "privacy", "environment"][i % 4],
                severity=sevs[i % 4],
                title=titles[i % len(titles)] + f" #{i + 1}",
                message=f"{msg}{i + 1}：" + (detail * (1 + i % 3)),
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


def _program_from_placements(placements: list[dict], *, locale_en: bool = False) -> dict:
    rooms = []
    for p in placements:
        name = f"Room {p['room_id'][1:]}" if locale_en else f"房间{p['room_id'][1:]}"
        rooms.append(
            {
                "id": p["room_id"],
                "name": name,
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
    locale_en: bool = False,
) -> dict:
    placements = _placements(floor_ids, rooms_per_floor)
    floor_svgs = {fid: _svg(label=fid) for fid in floor_ids}
    return {
        "id": "c-smoke",
        "seed": 42,
        "score": 75.0,
        "label": "A",
        "svg": _svg(label="+".join(floor_ids)),
        "floor_svgs": floor_svgs,
        "design_score": _score(
            n_findings=n_findings, locale_en=locale_en
        ).model_dump(mode="json"),
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


def _build(
    *,
    project_name: str,
    floor_ids: list[str],
    locale: str,
    rooms_per_floor: int = 4,
    n_findings: int = 4,
    assumptions: list[dict] | None = None,
    unknowns: list[dict] | None = None,
    north_angle: float | None = 30.0,
) -> str:
    locale_en = locale.lower().startswith("en")
    cand = _candidate(
        floor_ids=floor_ids,
        rooms_per_floor=rooms_per_floor,
        n_findings=n_findings,
        locale_en=locale_en,
    )
    report = build_design_report(
        project_name=project_name,
        requirement_spec=_req(
            floor_count=len(floor_ids),
            assumptions=assumptions,
            unknowns=unknowns,
            north_angle=north_angle,
        ),
        program=_program_from_placements(cand["placements"], locale_en=locale_en),
        candidate=cand,
        export_mode="preview",
        locale=locale,
    )
    return render_report_html(report)


PRINT_CASES: list[tuple[str, str, dict]] = [
        (
            "P01_single_floor",
            "P01 · 单层 / 少房间",
            {
                "floor_ids": ["F1"],
                "rooms_per_floor": 3,
                "n_findings": 3,
                "project_name": "单层样本",
                "locale": "zh-CN",
            },
        ),
        (
            "P02_two_floor",
            "P02 · 两层 / 正常住宅",
            {
                "floor_ids": ["F1", "F2"],
                "rooms_per_floor": 5,
                "n_findings": 5,
                "project_name": "两层样本",
                "locale": "zh-CN",
            },
        ),
        (
            "P03_three_floor",
            "P03 · 三层",
            {
                "floor_ids": ["F1", "F2", "F3"],
                "rooms_per_floor": 4,
                "n_findings": 4,
                "project_name": "三层样本",
                "locale": "zh-CN",
            },
        ),
        (
            "P04_long_title",
            "P04 · 超长项目名",
            {
                "floor_ids": ["F1", "F2"],
                "rooms_per_floor": 4,
                "project_name": (
                    "江南水乡庭院式独栋住宅方案深化设计与业主沟通归档稿"
                    "——含南北向场地约束与多代同堂功能分区说明"
                ),
                "locale": "zh-CN",
            },
        ),
        (
            "P05_many_rooms",
            "P05 · 房间较多",
            {
                "floor_ids": ["F1", "F2"],
                "rooms_per_floor": 14,
                "project_name": "多房间面积表",
                "locale": "zh-CN",
            },
        ),
        (
            "P06_many_findings",
            "P06 · Findings 很多",
            {
                "floor_ids": ["F1", "F2"],
                "rooms_per_floor": 5,
                "n_findings": 24,
                "project_name": "Findings 压力",
                "locale": "zh-CN",
            },
        ),
        (
            "P07_blocking_unknown",
            "P07 · Blocking Unknown",
            {
                "floor_ids": ["F1", "F2"],
                "rooms_per_floor": 4,
                "project_name": "Blocking Unknown",
                "locale": "zh-CN",
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
            },
        ),
        (
            "P08_locale_en",
            "P08 · en-US",
            {
                "floor_ids": ["F1", "F2"],
                "rooms_per_floor": 5,
                "n_findings": 6,
                "project_name": "Print Smoke EN Sample",
                "locale": "en",
                "north_angle": 45.0,
            },
        ),
    ]


def _case_kwargs(case_id: str) -> tuple[str, str, dict]:
    for cid, title, kwargs in PRINT_CASES:
        if cid == case_id:
            return cid, title, dict(kwargs)
    raise KeyError(case_id)


def desktop_project_payload(case_id: str) -> dict:
    """构建可写入 /api/projects 的 Desktop 手测项目（与 HTML 样本同数据）。"""
    from packages.schema.identity import (
        EVALUATION_VERSION,
        GENERATOR_VERSION,
        SELECTION_VERSION,
        SOLVER_VERSION,
    )

    _, _, raw = _case_kwargs(case_id)
    kwargs = dict(raw)
    floor_ids = kwargs.pop("floor_ids")
    locale = kwargs.pop("locale", "zh-CN")
    project_name = kwargs.pop("project_name", case_id)
    locale_en = locale.lower().startswith("en")
    cand = _candidate(
        floor_ids=floor_ids,
        rooms_per_floor=kwargs.get("rooms_per_floor", 4),
        n_findings=kwargs.get("n_findings", 4),
        locale_en=locale_en,
    )
    rid = f"print-{case_id}"
    cand["id"] = rid
    cand["revision_id"] = f"{rid}:gen:hand"
    cand["revision_status"] = "generated"
    req = _req(
        floor_count=len(floor_ids),
        assumptions=kwargs.get("assumptions"),
        unknowns=kwargs.get("unknowns"),
        north_angle=kwargs.get("north_angle", 30.0),
    )
    program = _program_from_placements(cand["placements"], locale_en=locale_en)
    return {
        "name": f"PrintHand-{case_id}",
        "payload": {
            "form": {"width": 11, "depth": 13, "floors": len(floor_ids)},
            "requirement_spec": req,
            "program": program,
            "locks": {"rooms": [], "stair": None, "zones": []},
            "candidates": [cand],
            "selected_id": rid,
            "schema_versions": {
                "solver_version": SOLVER_VERSION,
                "generator_strategy": "guillotine",
                "generator_version": GENERATOR_VERSION,
                "selection_strategy": "axis-diverse",
                "selection_version": SELECTION_VERSION,
                "evaluation_version": EVALUATION_VERSION,
                "assignment_strategy": "heuristic",
                "geometry_backend": "rect",
            },
        },
    }


def seed_desktop_projects(case_ids: list[str]) -> None:
    """写入 Desktop 手测项目（与 HTML 样本同数据）。"""
    import json
    import os
    import urllib.error
    import urllib.request

    host = os.environ.get("PLANSEED_HOST", "127.0.0.1")
    port = os.environ.get("PLANSEED_PORT", "8787")
    base = f"http://{host}:{port}"
    valid = {c[0] for c in PRINT_CASES}
    for case_id in case_ids:
        if case_id not in valid:
            raise SystemExit(f"Unknown case {case_id!r}")
        body = desktop_project_payload(case_id)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/projects",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                saved = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise SystemExit(
                f"POST /api/projects failed {e.code}: {e.read()[:300]!r}"
            ) from e
        print(f"OK: {saved['name']}  id={saved['id']}")
    print("")
    print("Desktop: Open project picker -> PrintHand-* -> Export -> Report preview")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # 清掉旧编号样本，避免与 P01–P08 混淆
    for old in OUT.glob("*.html"):
        old.unlink()

    rows: list[tuple[str, str, str]] = []
    print(f"generating → {OUT}")

    cases = PRINT_CASES

    for case_id, title, kwargs in cases:
        floor_ids = kwargs.pop("floor_ids")
        locale = kwargs.pop("locale", "zh-CN")
        html = _build(floor_ids=floor_ids, locale=locale, **kwargs)
        path = OUT / f"{case_id}.html"
        path.write_text(html, encoding="utf-8")
        rows.append((case_id, title, path.name))
        print(f"  wrote {path.relative_to(ROOT)}")

    index = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'/>",
        "<title>PlanSeed 7.1.1-C Print Smoke P01–P08</title>",
        "<style>body{font:14px/1.5 system-ui,sans-serif;max-width:42rem;",
        "margin:2rem auto;padding:0 1rem} li{margin:.4rem 0}</style></head><body>",
        "<h1>7.1.1-C Print Samples (P01–P08)</h1>",
        "<p><strong>关门验收：</strong>Windows · Tauri · WebView2 · "
        "Microsoft Print to PDF。</p>",
        "<p>清单：<code>docs/phase-7.1-print-smoke.md</code>。"
        "Edge 打开仅作对照，不能代替 Desktop。</p>",
        "<ol>",
    ]
    for case_id, title, name in rows:
        index.append(f'<li><a href="{name}">{case_id}</a> — {title}</li>')
    index.extend(
        [
            "</ol>",
            "<p>每份检查：封面 · 目录 · SVG 切页 · 独页平面 · 表跨页 · "
            "Findings · 中/英字体 · 边距 · 北针 · 面积表 · 页脚。</p>",
            "</body></html>",
        ]
    )
    (OUT / "index.html").write_text("\n".join(index), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT) / 'index.html'}")
    print("done. Hand-test in Desktop — no screenshot diff.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 7.1.1-C print smoke fixtures")
    parser.add_argument(
        "--seed-desktop",
        action="store_true",
        help="Write P02/P06 (or --cases) projects to running engine for Desktop hand-test",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=["P02_two_floor", "P06_many_findings"],
        help="Case ids for --seed-desktop",
    )
    args = parser.parse_args()
    if args.seed_desktop:
        print("== seed print hand-test projects ==")
        seed_desktop_projects(args.cases)
    else:
        main()

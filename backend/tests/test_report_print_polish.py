"""Phase 7.2.4 — Print polish：CSS 契约（非 PDF 引擎 / 非截图 diff）。"""

from __future__ import annotations

from backend.services.report_builder import build_design_report
from backend.services.report_html import render_report_html
from packages.schema.scoring import DesignScore


def _score() -> dict:
    return DesignScore(
        program_score=80,
        spatial_score=78,
        circulation_score=75,
        privacy_score=80,
        environment_score=70,
        technical_score=76,
        robustness_score=74,
        total_score=76.0,
        findings=[],
    ).model_dump(mode="json")


def _svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
        '<rect width="100" height="80" fill="#eee"/></svg>'
    )


def _candidate() -> dict:
    return {
        "id": "c-print",
        "seed": 1,
        "score": 76.0,
        "label": "A",
        "svg": _svg(),
        "floor_svgs": {"F1": _svg(), "F2": _svg()},
        "design_score": _score(),
        "provenance": {
            "solver_version": "s",
            "generator_version": "g",
            "evaluation_version": "e",
        },
        "revision_status": "generated",
        "revision_id": "c-print:gen:1",
        "placements": [
            {
                "room_id": "r1",
                "floor_id": "F1",
                "x": 0,
                "y": 0,
                "width": 4.0,
                "depth": 3.5,
                "area": 14.0,
            }
        ],
        "validation": {"valid": True, "hard_violations": [], "soft_violations": []},
    }


def _html() -> str:
    report = build_design_report(
        project_name="打印硬化",
        project_id="p1",
        requirement_spec={
            "floor_count": 2,
            "household": {"bedrooms": 3, "bathrooms": 2, "has_garage": False},
            "site": {"width": 11, "depth": 13},
            "spaces": [],
        },
        program={
            "rooms": [
                {"id": "r1", "name": "客厅", "category": "living", "target_area": 20}
            ]
        },
        candidate=_candidate(),
        export_mode="final",
    )
    return render_report_html(report)


def test_print_css_has_apage_and_a4():
    doc = _html()
    assert "@page" in doc
    assert "size: A4" in doc
    assert "margin:" in doc.split("@page")[1].split("}")[0]


def test_print_css_cover_and_plan_page_breaks():
    doc = _html()
    assert ".cover" in doc
    assert "page-break-after: always" in doc
    assert ".plan-page" in doc
    assert "break-after: page" in doc


def test_print_css_orphans_widows_and_table_header():
    doc = _html()
    assert "orphans: 3" in doc
    assert "widows: 3" in doc
    assert "table-header-group" in doc
    assert "thead" in doc


def test_print_css_no_blanket_chapter_avoid():
    """整章 break-inside:avoid 会在长表/多平面时制造空白页。"""
    doc = _html()
    print_block = doc.split("@media print")[1]
    assert ".chapter { break-inside: avoid" not in print_block
    assert ".chapter{break-inside:avoid" not in print_block.replace(" ", "")


def test_print_scale_copy_not_fake_ratio():
    doc = _html()
    assert "1:100" not in doc
    assert "1:50" not in doc
    assert "方案示意" in doc or "metres" in doc


def test_print_color_adjust_exact():
    doc = _html()
    assert "print-color-adjust: exact" in doc

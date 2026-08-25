"""Design Benchmark v2 — smoke / structure。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.schema.provenance import geometry_backend_for
from solver.benchmark.design_acceptance import (
    compute_ab_rate,
    format_acceptance_table,
    merge_grades,
    run_design_suite_acceptance,
)
from solver.fixtures.design_suite_v2 import (
    SUITE_ID,
    WAVE1_CASE_IDS,
    WAVE_SITE_CASE_IDS,
    list_suite_case_ids,
    load_suite_case,
)


def test_design_v2_wave1_catalog():
    ids = list_suite_case_ids(wave="core")
    assert ids == list(WAVE1_CASE_IDS)


def test_design_v2_wave2_site_catalog():
    ids = list_suite_case_ids(wave="site")
    assert ids == list(WAVE_SITE_CASE_IDS)


def test_design_v2_full_catalog():
    ids = list_suite_case_ids()
    assert len(ids) == 12
    assert ids[0] == "B01" and ids[-1] == "B12"


def test_design_cases_build_programs():
    for cid in list_suite_case_ids():
        case = load_suite_case(cid)
        assert case.meta.id == cid
        assert case.program.rooms
        assert case.program.floors
        assert case.meta.d_grade_hints
        if cid <= "B07":
            assert case.meta.tier == "core"
        else:
            assert case.meta.tier == "site"


def test_b05_elder_on_first_floor():
    case = load_suite_case("B05")
    elder = next(r for r in case.program.rooms if r.id == "elder")
    assert elder.floor_id == "F1"
    floor_ids = {
        c.room_id: c.floor_id for c in case.program.constraints if c.kind == "floor"
    }
    assert floor_ids.get("elder") == "F1"


def test_b07_four_bedrooms_second_floor():
    case = load_suite_case("B07")
    beds = [r for r in case.program.rooms if r.category.value == "private"]
    assert len(beds) == 4
    assert all(r.floor_id == "F2" for r in beds)


def test_b09_l_shape_buildable():
    pytest.importorskip("shapely")
    case = load_suite_case("B09")
    program = case.program
    assert program.site.site_polygon is not None
    assert program.buildable_polygon is not None
    assert len(program.buildable_free_rects) >= 2
    assert geometry_backend_for(program) == "shapely-orthogonal"


def test_b12_high_setbacks():
    case = load_suite_case("B12")
    sb = case.program.site.setbacks
    assert sb.north == 3 and sb.south == 2
    assert case.program.site.setback_source == "user"
    assert case.program.buildable.width < case.program.site.width


def test_design_v2_smoke_subset():
    report = run_design_suite_acceptance(
        candidate_count=2,
        case_ids=["B01", "B09"],
    )
    assert report.suite_id == SUITE_ID
    assert len(report.cases) == 2
    for case in report.cases:
        assert case.candidate_count == 2
        assert len(case.candidates) == 2
        assert case.ab_rate is None
        for cand in case.candidates:
            assert cand.auto_grade in ("", "D")
            assert cand.fingerprint
    table = format_acceptance_table(report)
    assert "B01" in table
    assert "B09" in table
    assert "ab_rate pending" in table


def test_merge_grades_computes_ab_rate(tmp_path: Path):
    report = run_design_suite_acceptance(candidate_count=2, case_ids=["B01"])
    grades = {
        "suite": SUITE_ID,
        "grades": {
            "B01": {
                "0": {"grade": "A"},
                "1": {"grade": "C"},
            }
        },
    }
    grades_path = tmp_path / "grades.json"
    grades_path.write_text(json.dumps(grades), encoding="utf-8")
    merge_grades(report, grades_path)
    assert report.grades_merged
    assert report.cases[0].ab_rate == 0.5
    assert report.aggregate["ab_rate"] == 0.5


def test_compute_ab_rate_invalid_auto_d():
    from solver.benchmark.design_acceptance import CandidateAcceptanceRecord

    records = [
        CandidateAcceptanceRecord(
            index=0,
            seed=42,
            valid=False,
            auto_grade="D",
            fingerprint="a",
            total_score=0.0,
            axis_scores={},
            metrics_proxy={},
            findings_summary=[],
            hard_violation_count=1,
        ),
        CandidateAcceptanceRecord(
            index=1,
            seed=43,
            valid=True,
            auto_grade="",
            fingerprint="b",
            total_score=80.0,
            axis_scores={},
            metrics_proxy={},
            findings_summary=[],
            hard_violation_count=0,
            human_grade="B",
        ),
    ]
    assert compute_ab_rate(records) == 0.5

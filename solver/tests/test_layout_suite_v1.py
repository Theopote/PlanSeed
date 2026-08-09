"""Layout Benchmark Suite v1 — smoke / structure。"""

from __future__ import annotations

from solver.benchmark.layout_generation import (
    format_suite_table,
    run_layout_suite_benchmark,
)
from solver.fixtures.layout_suite_v1 import (
    SUITE_ID,
    list_suite_case_ids,
    load_suite_case,
)


def test_suite_v1_case_catalog():
    ids = list_suite_case_ids()
    assert ids == [
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B09",
        "B10",
        "B11",
        "B12",
    ]


def test_suite_cases_build_programs():
    for cid in list_suite_case_ids():
        case = load_suite_case(cid)
        assert case.meta.id == cid
        assert case.program.rooms
        assert case.program.floors
        if cid in ("B11", "B12"):
            assert case.locks is not None
            if cid == "B11":
                assert case.locks.rooms
            else:
                assert case.locks.zones


def test_suite_v1_smoke_subset():
    """CI smoke：少量 seeds × 子集 cases；完整资格跑 --count 32/64。"""
    report = run_layout_suite_benchmark(
        candidate_count=2,
        case_ids=["B01", "B03", "B11"],
    )
    assert report.suite_id == SUITE_ID
    assert len(report.cases) == 3
    assert set(report.aggregate) == {"guillotine", "maxrect"}
    for case in report.cases:
        assert {s.strategy_id for s in case.strategies} == {"guillotine", "maxrect"}
        for s in case.strategies:
            assert hasattr(s, "privacy")
            assert hasattr(s, "environment")
            assert hasattr(s, "mean_repair_count")
            assert 0.0 <= s.valid_rate <= 1.0
    table = format_suite_table(report)
    assert "B01" in table
    assert "aggregate" in table
    assert "asp_pen" in table

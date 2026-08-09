"""Phase 8.0-C — layout-generation-benchmark。"""

from __future__ import annotations

from solver.benchmark.layout_generation import (
    format_report_table,
    run_layout_generation_benchmark,
    run_strategy_benchmark,
)
from solver.fixtures.benchmark import benchmark_program
from solver.generators import GuillotineGenerator, MaxRectGenerator


def test_benchmark_compare_guillotine_maxrect_smoke():
    report = run_layout_generation_benchmark(candidate_count=4)
    ids = {s.strategy_id for s in report.strategies}
    assert ids == {"guillotine", "maxrect"}
    assert report.candidate_count == 4
    assert "guillotine__vs__maxrect" in report.pairwise_geometry_diff_rate
    # 同 seed 应产生不同几何分布（8.0-B 目标）
    assert report.pairwise_geometry_diff_rate["guillotine__vs__maxrect"] > 0.0

    for s in report.strategies:
        assert s.candidate_count == 4
        assert 0.0 <= s.valid_rate <= 1.0
        assert 0.0 <= s.hard_violation_rate <= 1.0
        assert 0.0 <= s.diversity <= 1.0
        assert s.runtime_s >= 0.0
        assert s.distinct_layouts >= 1
        assert s.privacy >= 0.0
        assert s.environment >= 0.0
        assert s.mean_repair_count >= 0.0


def test_benchmark_deterministic_metrics():
    program = benchmark_program()
    a, _ = run_strategy_benchmark(
        GuillotineGenerator(), program, candidate_count=3
    )
    b, _ = run_strategy_benchmark(
        GuillotineGenerator(), program, candidate_count=3
    )
    da, db = a.to_dict(), b.to_dict()
    da.pop("runtime_s")
    db.pop("runtime_s")
    assert da == db


def test_format_report_table_contains_strategies():
    report = run_layout_generation_benchmark(candidate_count=2)
    table = format_report_table(report)
    assert "guillotine" in table
    assert "maxrect" in table
    assert "pairwise geometry diff rate" in table


def test_maxrect_strategy_benchmark_runs():
    m, result = run_strategy_benchmark(
        MaxRectGenerator(), benchmark_program(), candidate_count=2
    )
    assert m.strategy_id == "maxrect"
    assert m.generator_version == "maxrect-v1"
    assert result.generated == 2

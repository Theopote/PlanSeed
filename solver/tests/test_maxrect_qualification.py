"""MaxRect qualification gate 单元测试。"""

from __future__ import annotations

from solver.benchmark.layout_generation import (
    LayoutGenerationBenchmarkReport,
    LayoutSuiteBenchmarkReport,
    StrategyMetrics,
)
from solver.benchmark.maxrect_qualification import (
    AGGREGATE_ASPECT_PENALTY_RATIO_MAX,
    evaluate_case,
    evaluate_maxrect_qualification,
)


def _metrics(
    strategy_id: str,
    *,
    valid_rate: float,
    aspect_pen: float,
    top_score: float,
) -> StrategyMetrics:
    return StrategyMetrics(
        strategy_id=strategy_id,
        generator_version="test",
        candidate_count=32,
        runtime_s=1.0,
        valid_rate=valid_rate,
        hard_violation_rate=0.0,
        mean_hard_violations=0.0,
        area_fit=0.75,
        aspect_ratio_quality=1.0 / (1.0 + aspect_pen),
        mean_aspect_ratio_penalty=aspect_pen,
        circulation=75.0,
        privacy=80.0,
        environment=70.0,
        orientation=0.8,
        mean_repair_count=0.0,
        diversity=0.9,
        distinct_layouts=28,
        distinct_valid=28,
        top_score=top_score,
        mean_score=top_score - 2.0,
    )


def _case(
    case_id: str,
    g_valid: float,
    m_valid: float,
    g_pen: float,
    m_pen: float,
    g_top: float,
    m_top: float,
) -> LayoutGenerationBenchmarkReport:
    return LayoutGenerationBenchmarkReport(
        case=case_id,
        case_title=case_id,
        strategies=[
            _metrics("guillotine", valid_rate=g_valid, aspect_pen=g_pen, top_score=g_top),
            _metrics("maxrect", valid_rate=m_valid, aspect_pen=m_pen, top_score=m_top),
        ],
    )


def test_case_passes_when_metrics_close():
    case = _case("B03", 1.0, 1.0, 30.0, 50.0, 90.0, 88.0)
    result = evaluate_case(case)
    assert result.passed
    assert result.aspect_penalty_ratio is not None
    assert result.aspect_penalty_ratio < 3.0


def test_case_fails_on_aspect_penalty_ratio():
    case = _case("B03", 1.0, 1.0, 28.0, 166.0, 92.0, 89.0)
    result = evaluate_case(case)
    assert not result.passed
    assert any("aspect_penalty ratio" in f for f in result.failures)


def test_suite_gate_fails_on_known_b03_pattern():
    suite = LayoutSuiteBenchmarkReport(
        candidate_count=32,
        cases=[
            _case("B01", 1.0, 1.0, 20.0, 25.0, 85.0, 84.0),
            _case("B03", 1.0, 1.0, 28.67, 166.79, 92.31, 89.08),
        ],
        aggregate={
            "guillotine": {
                "valid_rate": 1.0,
                "mean_aspect_ratio_penalty": 24.0,
                "top_score": 88.0,
            },
            "maxrect": {
                "valid_rate": 1.0,
                "mean_aspect_ratio_penalty": 95.0,
                "top_score": 87.0,
            },
        },
    )
    qual = evaluate_maxrect_qualification(suite)
    assert not qual.passed
    assert qual.aggregate_aspect_penalty_ratio is not None
    assert qual.aggregate_aspect_penalty_ratio > AGGREGATE_ASPECT_PENALTY_RATIO_MAX

"""Quality regression — 防止「门槛过低、测试空转」。"""

from __future__ import annotations

from solver.pipeline import run_pipeline
from solver.tests.quality_baselines import DEFAULT_QUALITY, MEASURED_BASELINE
from solver.tests.test_guillotine import benchmark_program


def _fingerprint(candidate) -> str:
    """布局指纹：几何 + core 区位（忽略 score/metrics）。"""
    payload = candidate.model_dump(
        exclude={"score", "metrics", "validation", "evaluation"},
    )
    import json

    return json.dumps(payload, sort_keys=True, default=str)


class TestQualityRegression:
    """
    基准案例流水线质量回归。

    阈值见 quality_baselines.py；收紧前先对照 MEASURED_BASELINE。
    """

    def test_valid_ratio_above_threshold(self):
        program = benchmark_program()
        result = run_pipeline(program)
        q = DEFAULT_QUALITY
        assert result.generated == q.candidate_count
        ratio = result.valid / result.generated
        assert ratio >= q.min_valid_ratio, (
            f"valid_ratio={ratio:.3f} < {q.min_valid_ratio} "
            f"(valid={result.valid}/{result.generated}; "
            f"baseline≈{MEASURED_BASELINE['valid_ratio']})"
        )

    def test_distinct_layouts_above_threshold(self):
        program = benchmark_program()
        result = run_pipeline(program)
        q = DEFAULT_QUALITY
        fingerprints = {_fingerprint(c) for c in result.all_candidates}
        assert len(fingerprints) >= q.min_distinct_layouts, (
            f"distinct={len(fingerprints)} < {q.min_distinct_layouts} "
            f"(baseline={MEASURED_BASELINE['distinct_layouts']})"
        )

    def test_distinct_valid_layouts_above_threshold(self):
        program = benchmark_program()
        result = run_pipeline(program)
        q = DEFAULT_QUALITY
        valid = [c for c in result.all_candidates if c.validation and c.validation.valid]
        fingerprints = {_fingerprint(c) for c in valid}
        assert len(fingerprints) >= q.min_distinct_valid, (
            f"distinct_valid={len(fingerprints)} < {q.min_distinct_valid} "
            f"(baseline={MEASURED_BASELINE['distinct_valid']})"
        )

    def test_top_k_have_no_hard_violations(self):
        program = benchmark_program()
        result = run_pipeline(program)
        q = DEFAULT_QUALITY
        top = result.top_candidates
        assert len(top) == q.min_top_k
        for c in top:
            assert c.validation is not None
            if q.require_top_all_valid:
                assert c.validation.valid, f"Top seed={c.seed} invalid"
            assert c.validation.hard_violations == [], (
                f"Top seed={c.seed} hard_violations={c.validation.hard_violations}"
            )
            assert c.score is not None and c.score > 0

    def test_top_k_area_accuracy_above_threshold(self):
        program = benchmark_program()
        result = run_pipeline(program)
        q = DEFAULT_QUALITY
        for c in result.top_candidates:
            aa = float(c.metrics.get("area_accuracy", 0.0))
            assert aa >= q.min_top_area_accuracy, (
                f"Top seed={c.seed} area_accuracy={aa:.4f} < {q.min_top_area_accuracy} "
                f"(baseline≈{MEASURED_BASELINE['top_area_accuracy']})"
            )

    def test_core_placement_diversity(self):
        """seed 应驱动多种 StairCore 区位，而非永远贴西。"""
        program = benchmark_program()
        result = run_pipeline(program)
        q = DEFAULT_QUALITY
        placements = {
            c.floors[0].core_placement
            for c in result.all_candidates
            if c.floors and c.floors[0].core_placement
        }
        assert len(placements) >= q.min_core_placements, (
            f"core_placements={placements} count={len(placements)} "
            f"< {q.min_core_placements}"
        )

    def test_baseline_not_silently_worse_than_recorded(self):
        """
        软对照：当前结果不应显著差于已记录基线。

        使用比正式门槛更紧、但仍低于 MEASURED 的缓冲带，
        用于发现「缓慢退化」。
        """
        program = benchmark_program()
        result = run_pipeline(program)
        ratio = result.valid / result.generated
        # 允许相对基线掉 10 个百分点，但仍须 ≥ 正式门槛
        soft_floor = max(DEFAULT_QUALITY.min_valid_ratio, MEASURED_BASELINE["valid_ratio"] - 0.10)
        assert ratio >= soft_floor, (
            f"valid_ratio 相对基线退化过多: {ratio:.3f} < soft_floor {soft_floor:.3f} "
            f"(measured={MEASURED_BASELINE['valid_ratio']})"
        )

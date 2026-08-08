"""Metric Ownership — 映射七轴，禁止重复计分。"""

from __future__ import annotations

from solver.evaluation.geometry import geometry_score
from solver.evaluation.ownership import METRIC_OWNER, owner_of
from solver.evaluation.program_fit import program_fit_score, space_efficiency_score
from solver.evaluation.score import CompositeEvaluator
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program


class TestMetricOwnership:
    def test_owner_map_unique_for_overlap_risks(self):
        assert owner_of("area_accuracy") == "program"
        assert owner_of("aspect_ratio_penalty") == "spatial"
        assert owner_of("slender_room_count") == "spatial"
        assert owner_of("compactness") == "spatial"
        assert owner_of("layout_stability") == "robustness"
        assert len(METRIC_OWNER) == len(set(METRIC_OWNER))

    def test_geometry_ignores_area_and_compactness(self):
        bad_area = {
            "area_accuracy": 0.1,
            "compactness": 0.1,
            "aspect_ratio_penalty": 0.0,
            "slender_room_count": 0.0,
        }
        good_area = {
            "area_accuracy": 1.0,
            "compactness": 1.0,
            "aspect_ratio_penalty": 0.0,
            "slender_room_count": 0.0,
        }
        assert geometry_score(bad_area) == geometry_score(good_area)

    def test_space_efficiency_ignores_slender(self):
        compact = {"space_efficiency": 0.9, "slender_room_ratio": 0.0}
        slender = {"space_efficiency": 0.9, "slender_room_ratio": 0.9}
        assert space_efficiency_score(compact) == space_efficiency_score(slender)

    def test_program_fit_owns_area(self):
        low = {"program_fit": 0.5}
        high = {"program_fit": 0.95}
        assert program_fit_score(low) < program_fit_score(high)

    def test_seven_axis_design_score(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        score = CompositeEvaluator().evaluate(program, candidate)
        for attr in (
            "program_score",
            "spatial_score",
            "circulation_score",
            "privacy_score",
            "environment_score",
            "technical_score",
            "robustness_score",
        ):
            assert getattr(score, attr) >= 0
        assert score.total_score > 0

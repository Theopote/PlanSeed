"""Metric Ownership — 禁止同一原始 metric 重复计入多个 score。"""

from __future__ import annotations

from solver.evaluation.geometry import geometry_score
from solver.evaluation.ownership import METRIC_OWNER, owner_of
from solver.evaluation.program_fit import program_fit_score, space_efficiency_score


class TestMetricOwnership:
    def test_owner_map_unique_for_overlap_risks(self):
        assert owner_of("area_accuracy") == "program_fit"
        assert owner_of("aspect_ratio_penalty") == "geometry"
        assert owner_of("slender_room_count") == "geometry"
        assert owner_of("compactness") == "space_efficiency"
        # 同一 primary 可拥有多个 metric；禁止一个 metric 多 owner（字典保证）
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
        # space_efficiency_score 只读 space_efficiency 键
        assert space_efficiency_score(compact) == space_efficiency_score(slender)

    def test_program_fit_owns_area(self):
        low = {"program_fit": 0.5, "program_coverage": 1.0, "program_area_accuracy": 0.1}
        high = {"program_fit": 0.95, "program_coverage": 1.0, "program_area_accuracy": 0.95}
        assert program_fit_score(low) < program_fit_score(high)

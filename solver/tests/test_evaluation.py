"""几何评价与面积份额准确性。"""

from __future__ import annotations

from packages.schema.layout import PlacementRect, PlacementSource, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.site import Rect2D, SiteSpec
from solver.evaluation.geometry import _proportional_area_accuracy, compute_geometry_metrics
from solver.evaluation.score import CompositeEvaluator
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program


def _placement(room_id: str, floor_id: str, area_as_width: float) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id=floor_id,
        rect=PlacementRect(x=0, y=0, width=area_as_width, depth=1.0),
        source=PlacementSource.PROGRAM,
        category=RoomCategory.PUBLIC.value,
    )


class TestAreaAccuracy:
    def test_perfect_share_match(self):
        program = DesignProgram(
            project_id="t",
            site=SiteSpec(width=11, depth=13),
            buildable=Rect2D(x=0, y=0, width=11, depth=13),
            floors=[{"id": "F1", "label": "一层", "room_ids": ["a", "b"]}],
            rooms=[
                RoomSpec(id="a", name="A", category=RoomCategory.PUBLIC, target_area=30),
                RoomSpec(id="b", name="B", category=RoomCategory.OTHER, target_area=10),
            ],
            constraints=[],
        )
        placements = [_placement("a", "F1", 6.0), _placement("b", "F1", 2.0)]
        assert _proportional_area_accuracy(program, placements) == 1.0

    def test_mismatched_shares_lower(self):
        program = DesignProgram(
            project_id="t",
            site=SiteSpec(width=11, depth=13),
            buildable=Rect2D(x=0, y=0, width=11, depth=13),
            floors=[{"id": "F1", "label": "一层", "room_ids": ["a", "b"]}],
            rooms=[
                RoomSpec(id="a", name="A", category=RoomCategory.PUBLIC, target_area=30),
                RoomSpec(id="b", name="B", category=RoomCategory.OTHER, target_area=10),
            ],
            constraints=[],
        )
        # 实际份额对调：50/50 vs 目标 75/25
        placements = [_placement("a", "F1", 5.0), _placement("b", "F1", 5.0)]
        acc = _proportional_area_accuracy(program, placements)
        assert 0.0 < acc < 1.0

    def test_benchmark_pipeline_area_accuracy_nonzero(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        metrics = compute_geometry_metrics(program, candidate)
        assert metrics["area_accuracy"] > 0.5

    def test_evaluated_score_uses_share_accuracy(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        score = CompositeEvaluator().evaluate(program, candidate)
        assert score.metrics.area_error < 0.5
        assert candidate.metrics["area_accuracy"] > 0.5

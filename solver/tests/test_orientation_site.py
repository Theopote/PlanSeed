"""Orientation / Site 评价闭环测试。"""

from __future__ import annotations

from packages.schema.constraints import ConstraintSource, OrientationConstraint
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import Rect2D, SiteSpec
from solver.evaluation.orientation import (
    compute_orientation_metrics,
    exterior_orientations,
    orientation_score,
    orientation_soft_violations,
)
from solver.evaluation.score import CompositeEvaluator
from solver.evaluation.site import compute_site_metrics, site_score
from solver.geometry.rect import Rect
from solver.tests.test_guillotine import benchmark_program
from solver.generators.guillotine import GuillotineGenerator


def _program_with_orientation(preferred: str = "south") -> DesignProgram:
    program = benchmark_program()
    program.constraints.append(
        OrientationConstraint(
            id="orient-living-south",
            room_id="r1",
            preferred_orientation=preferred,
            hard=False,
            weight=0.8,
            source=ConstraintSource.NORMALIZER,
            source_key="preferences.prefer_south_facing_living",
            description="客厅优先朝南",
        )
    )
    return program


def _candidate_living_on_edge(edge: str) -> LayoutCandidate:
    """手工放置客厅贴某外墙。buildable 11×13，y=0 北。"""
    if edge == "south":
        rect = PlacementRect(x=2, y=10, width=4, depth=3)  # bottom=13
    elif edge == "north":
        rect = PlacementRect(x=2, y=0, width=4, depth=3)
    elif edge == "west":
        rect = PlacementRect(x=0, y=4, width=3, depth=4)
    else:
        rect = PlacementRect(x=8, y=4, width=3, depth=4)

    living = RoomPlacement(
        room_id="r1",
        floor_id="F1",
        rect=rect,
        source=PlacementSource.PROGRAM,
        name="客厅",
        category="public",
    )
    return LayoutCandidate(
        id="orient-test",
        seed=0,
        floors=[FloorLayout(floor_id="F1", placements=[living])],
    )


class TestOrientationEvaluator:
    def test_exterior_orientations_south(self):
        buildable = Rect(x=0, y=0, width=11, depth=13)
        room = Rect(x=2, y=10, width=4, depth=3)
        assert "south" in exterior_orientations(room, buildable)

    def test_south_facing_living_scores_higher_than_north(self):
        program = _program_with_orientation("south")
        south = _candidate_living_on_edge("south")
        north = _candidate_living_on_edge("north")
        m_south = compute_orientation_metrics(program, south)
        m_north = compute_orientation_metrics(program, north)
        assert m_south["orientation_satisfaction"] == 1.0
        assert m_north["orientation_satisfaction"] == 0.0
        assert orientation_score(m_south) > orientation_score(m_north)

    def test_soft_violation_explainable(self):
        program = _program_with_orientation("south")
        north = _candidate_living_on_edge("north")
        viols = orientation_soft_violations(program, north)
        assert len(viols) == 1
        assert viols[0].constraint_id == "orient-living-south"
        assert viols[0].hard is False
        assert "south" in viols[0].message

    def test_composite_includes_orientation_in_total(self):
        program = _program_with_orientation("south")
        # 用真实 generator：有的 seed 客厅可能贴南
        evaluator = CompositeEvaluator()
        scores = []
        for seed in range(16):
            c = GuillotineGenerator().generate(program, seed)
            # 仅评 orientation 相关：把客厅强制移到南/北再比
            pass
        south_c = GuillotineGenerator().generate(program, 0)
        # 覆盖 r1 矩形到南缘
        for fl in south_c.floors:
            for p in fl.placements:
                if p.room_id == "r1":
                    p.rect = PlacementRect(x=2, y=10, width=4, depth=3)
        north_c = south_c.model_copy(deep=True)
        for fl in north_c.floors:
            for p in fl.placements:
                if p.room_id == "r1":
                    p.rect = PlacementRect(x=2, y=0, width=4, depth=3)
        s_south = evaluator.evaluate(program, south_c)
        s_north = evaluator.evaluate(program, north_c)
        assert s_south.orientation_score > s_north.orientation_score
        assert s_south.total_score >= s_north.total_score
        assert s_north.violations


class TestSiteEvaluator:
    def test_no_setback_info_not_pretend_code_compliance(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        metrics = compute_site_metrics(program, candidate)
        assert metrics["setback_info_provided"] is False
        score = site_score(metrics)
        assert score <= 95.0

    def test_user_setbacks_reported(self):
        program = benchmark_program()
        program.site.setback_source = "user"
        program.site.setbacks.north = 1.0
        # rebuild envelope would need re-normalize; just flag
        candidate = GuillotineGenerator().generate(program, seed=0)
        metrics = compute_site_metrics(program, candidate)
        assert metrics["setback_info_provided"] is True

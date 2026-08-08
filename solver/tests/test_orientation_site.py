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
from packages.schema.site import CardinalEdge, CardinalOrientation
from solver.evaluation.orientation import (
    compute_orientation_metrics,
    exterior_model_edges,
    exterior_orientations,
    exterior_world_orientations,
    orientation_score,
    orientation_soft_violations,
)
from solver.evaluation.score import CompositeEvaluator
from solver.evaluation.site import compute_site_metrics, site_score
from solver.geometry.rect import Rect
from solver.geometry.site_coords import SiteCoordinateSystem, azimuth_to_cardinal
from solver.tests.test_guillotine import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from packages.schema.program import DesignProgram


def _program_with_orientation(
    preferred: str = "south",
    *,
    north_angle: float = 0.0,
) -> DesignProgram:
    program = benchmark_program()
    program.site.north_angle = north_angle
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
    """手工放置客厅贴某 model 外墙。buildable 11×13，y=0 = model north。"""
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


class TestSiteCoordinateSystem:
    def test_edge_azimuth_zero(self):
        cs = SiteCoordinateSystem(north_angle=0)
        assert cs.edge_azimuth(CardinalEdge.NORTH) == 0
        assert cs.edge_azimuth(CardinalEdge.EAST) == 90
        assert cs.edge_azimuth(CardinalEdge.SOUTH) == 180
        assert cs.edge_azimuth(CardinalEdge.WEST) == 270

    def test_edge_azimuth_rotated_90(self):
        cs = SiteCoordinateSystem(north_angle=90)
        assert cs.edge_azimuth("north") == 90
        assert cs.edge_azimuth("east") == 180
        assert cs.edge_azimuth("south") == 270
        assert cs.edge_azimuth("west") == 0
        assert cs.world_orientation_for_edge("north") == CardinalOrientation.EAST
        assert cs.world_orientation_for_edge("east") == CardinalOrientation.SOUTH
        assert cs.model_edges_facing("south") == {"east"}

    def test_azimuth_to_cardinal_sectors(self):
        assert azimuth_to_cardinal(0) == CardinalOrientation.NORTH
        assert azimuth_to_cardinal(44) == CardinalOrientation.NORTH
        assert azimuth_to_cardinal(45) == CardinalOrientation.EAST
        assert azimuth_to_cardinal(180) == CardinalOrientation.SOUTH


class TestOrientationEvaluator:
    def test_exterior_orientations_south_when_north_angle_zero(self):
        buildable = Rect(x=0, y=0, width=11, depth=13)
        room = Rect(x=2, y=10, width=4, depth=3)
        assert "south" in exterior_orientations(room, buildable, north_angle=0)
        assert exterior_model_edges(room, buildable) == {"south"}

    def test_north_angle_90_maps_model_east_to_world_south(self):
        buildable = Rect(x=0, y=0, width=11, depth=13)
        # 贴 model 东边
        room = Rect(x=8, y=4, width=3, depth=4)
        cs = SiteCoordinateSystem(north_angle=90)
        assert "east" in exterior_model_edges(room, buildable)
        worlds = exterior_world_orientations(room, buildable, cs)
        assert "south" in worlds
        assert "east" not in worlds  # model east ≠ world east when rotated

    def test_south_facing_living_scores_higher_than_north(self):
        program = _program_with_orientation("south", north_angle=0)
        south = _candidate_living_on_edge("south")
        north = _candidate_living_on_edge("north")
        m_south = compute_orientation_metrics(program, south)
        m_north = compute_orientation_metrics(program, north)
        assert m_south["orientation_satisfaction"] == 1.0
        assert m_north["orientation_satisfaction"] == 0.0
        assert orientation_score(m_south) > orientation_score(m_north)

    def test_preferred_south_with_north_angle_90_uses_model_east(self):
        """世界南 ≠ SVG 下边：north_angle=90 时应对齐 model 东边。"""
        program = _program_with_orientation("south", north_angle=90)
        on_model_east = _candidate_living_on_edge("east")
        on_model_south = _candidate_living_on_edge("south")
        m_east = compute_orientation_metrics(program, on_model_east)
        m_south = compute_orientation_metrics(program, on_model_south)
        assert m_east["orientation_satisfaction"] == 1.0
        assert m_south["orientation_satisfaction"] == 0.0
        assert m_east["north_angle"] == 90.0

    def test_soft_violation_explainable(self):
        program = _program_with_orientation("south", north_angle=0)
        north = _candidate_living_on_edge("north")
        viols = orientation_soft_violations(program, north)
        assert len(viols) == 1
        assert viols[0].constraint_id == "orient-living-south"
        assert viols[0].hard is False
        assert "south" in viols[0].message

    def test_composite_includes_orientation_in_total(self):
        program = _program_with_orientation("south", north_angle=0)
        evaluator = CompositeEvaluator()
        south_c = GuillotineGenerator().generate(program, 0)
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
        assert s_south.environment_score > s_north.environment_score
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
        candidate = GuillotineGenerator().generate(program, seed=0)
        metrics = compute_site_metrics(program, candidate)
        assert metrics["setback_info_provided"] is True

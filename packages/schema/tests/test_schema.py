"""Schema v2 单元测试 — Phase 0 第一批。"""

import json

import pytest
from pydantic import ValidationError

from packages.schema.constraints import (
    AdjacencyConstraint,
    ConstraintKind,
    ConstraintSource,
    WidthConstraint,
)
from packages.schema.layout import LayoutCandidate, PlacementRect, RoomPlacement
from packages.schema.project import ProjectSpec
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.scoring import DesignScore
from packages.schema.site import CardinalEdge, SiteSpec
from solver.program.normalize import build_room_graph, normalize


def _sample_project() -> ProjectSpec:
    """旧手册 Step 1 基准用例的 v2 表达。"""
    return ProjectSpec(
        id="bench-1",
        name="基准两层户型",
        site=SiteSpec(width=11, depth=13, stair_width=1.6, grid_module=0.3, structural_module=3.3),
        floors=[
            {"id": "F1", "label": "一层", "room_ids": ["r1", "r2", "r3", "r4"]},
            {"id": "F2", "label": "二层", "room_ids": ["r5", "r6", "r7", "r8", "r9", "r10"]},
        ],
        rooms=[
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="r2", name="餐厅+厨房", category=RoomCategory.WET, target_area=16, tags=["kitchen"]),
            RoomSpec(id="r3", name="卫生间", category=RoomCategory.WET, target_area=4),
            RoomSpec(id="r4", name="车库/储藏", category=RoomCategory.OTHER, target_area=15, tags=["garage"]),
            RoomSpec(id="r5", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="r6", name="主卫", category=RoomCategory.WET, target_area=5),
            RoomSpec(id="r7", name="次卧1", category=RoomCategory.PRIVATE, target_area=12),
            RoomSpec(id="r8", name="次卧2", category=RoomCategory.PRIVATE, target_area=12),
            RoomSpec(id="r9", name="公共卫生间", category=RoomCategory.WET, target_area=4),
            RoomSpec(id="r10", name="书房", category=RoomCategory.OTHER, target_area=9),
        ],
    )


class TestSiteSpec:
    def test_derives_site_boundary_and_buildable_envelope(self):
        site = SiteSpec(width=11, depth=13, setbacks={"north": 1, "south": 0.5, "east": 0.5, "west": 0.5})
        assert site.site_boundary is not None
        assert site.site_boundary.width == 11
        assert site.buildable_envelope is not None
        assert site.buildable_envelope.width == pytest.approx(10.0)
        assert site.buildable_envelope.depth == pytest.approx(11.5)

    def test_site_boundary_buildable_footprint_are_distinct_fields(self):
        site = SiteSpec(width=11, depth=13)
        assert site.site_boundary is not None
        assert site.buildable_envelope is not None
        assert site.building_footprint is None


class TestRoomSpec:
    def test_resolved_area_bounds(self):
        room = RoomSpec(
            id="r1",
            name="客厅",
            category=RoomCategory.PUBLIC,
            target_area=24,
            min_area=20,
            max_area=30,
        )
        assert room.resolved_min_area() == 20
        assert room.resolved_max_area() == 30

    def test_default_area_bounds_from_target(self):
        room = RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24)
        assert room.resolved_min_area() == pytest.approx(20.4)
        assert room.resolved_max_area() == pytest.approx(30.0)


class TestConstraints:
    def test_adjacency_constraint_defaults(self):
        c = AdjacencyConstraint(id="adj-1", room_a_id="r1", room_b_id="r2")
        assert c.kind == ConstraintKind.ADJACENCY
        assert c.hard is True
        assert c.weight == 1.0

    def test_width_constraint_hard_by_default(self):
        c = WidthConstraint(id="w-1", room_id="r3", min_width=1.5)
        assert c.hard is True
        assert c.min_width == 1.5


class TestLayoutCandidate:
    def test_room_placement_area_and_aspect_ratio(self):
        rect = PlacementRect(x=0, y=0, width=4, depth=2)
        p = RoomPlacement(room_id="r1", floor_id="F1", rect=rect)
        assert p.area == 8
        assert p.aspect_ratio == 2.0

    def test_layout_candidate_separates_from_room_spec(self):
        spec = _sample_project()
        candidate = LayoutCandidate(
            id="c-1",
            seed=42,
            floors=[],
        )
        assert "rect" not in RoomSpec.model_fields
        assert "rect" in RoomPlacement.model_fields
        assert candidate.seed == 42


class TestProjectSpec:
    def test_floor_count_and_room_lookup(self):
        spec = _sample_project()
        assert spec.floor_count == 2
        assert spec.room_by_id("r1").name == "客厅"
        assert len(spec.rooms_on_floor("F1")) == 4

    def test_json_schema_roundtrip(self):
        spec = _sample_project()
        schema = ProjectSpec.model_json_schema()
        assert "ProjectSpec" in schema.get("$defs", schema) or "properties" in schema
        payload = spec.model_dump_json()
        restored = ProjectSpec.model_validate_json(payload)
        assert restored.id == spec.id
        assert len(restored.rooms) == len(spec.rooms)

    def test_invalid_floor_count_rejected(self):
        with pytest.raises(ValidationError):
            ProjectSpec(
                site=SiteSpec(width=11, depth=13),
                floors=[],
                rooms=[RoomSpec(id="r1", name="x", category=RoomCategory.OTHER, target_area=10)],
            )


class TestNormalize:
    def test_normalize_produces_design_program(self):
        program = normalize(_sample_project())
        assert program.buildable.width == pytest.approx(11)
        assert program.buildable.depth == pytest.approx(13)
        assert len(program.rooms) == 10

    def test_implicit_width_constraint_has_source(self):
        spec = _sample_project()
        spec.rooms[2].min_width = 1.5
        program = normalize(spec)
        width_constraints = [c for c in program.constraints if c.kind == ConstraintKind.WIDTH]
        wc = next(c for c in width_constraints if c.room_id == "r3")
        assert wc.min_width == 1.5
        assert wc.source == ConstraintSource.NORMALIZER
        assert wc.source_key == "rooms.r3.min_width"

    def test_build_room_graph_includes_wet_near_edges(self):
        graph = build_room_graph(_sample_project())
        wet_ids = {"r2", "r3", "r6", "r9"}
        near_edges = [e for e in graph.edges if e.kind.value == "near"]
        assert all(e.source_id in wet_ids and e.target_id in wet_ids for e in near_edges)


class TestSpaceConnectionAccessGraph:
    def test_adjacency_is_not_circulation(self):
        """Kitchen—Dining 邻接 ≠ Hall—Bedroom 通行。"""
        from packages.schema.topology import (
            AccessGraph,
            SpaceConnection,
            SpaceConnectionType,
        )

        g = AccessGraph()
        g.add_connection(
            SpaceConnection(
                id="c1",
                a="hall",
                b="bed_a",
                type=SpaceConnectionType.DOOR,
                required=True,
            )
        )
        g.add_connection(
            SpaceConnection(
                id="c2",
                a="kitchen",
                b="dining",
                type=SpaceConnectionType.OPEN,
                required=False,
            )
        )
        assert set(g.node_ids) >= {"hall", "bed_a", "kitchen", "dining"}
        assert len(g.required_connections()) == 1
        assert g.required_connections()[0].type == SpaceConnectionType.DOOR


class TestDesignScore:
    def test_default_scores_are_zero(self):
        score = DesignScore()
        assert score.total_score == 0.0
        assert score.metrics.overlap_count == 0


class TestJsonSchemaForLLM:
    def test_schema_is_json_serializable(self):
        schema = ProjectSpec.model_json_schema()
        text = json.dumps(schema)
        assert "site" in text
        assert "rooms" in text

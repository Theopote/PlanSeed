"""RoomGraph helpers + semantic_role / entry / road 补测。"""

from __future__ import annotations

from packages.schema.entry import ExteriorEntrySpec
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec, SemanticRole
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import RoomEdge, RoomEdgeKind, RoomGraph
from solver.circulation.exterior_entry import resolve_entry_edge, resolve_exterior_entry
from solver.evaluation.site import compute_site_metrics
from solver.generators.guillotine import GuillotineGenerator
from solver.program.floor_assignment import FloorAssignmentSolver, ensure_floor_assignment
from solver.semantics.roles import is_master_bedroom
from solver.tests.test_guillotine import benchmark_program
from solver.topology.graph import (
    connected_components,
    degree,
    edges_for_room,
    has_edge,
)
from solver.visualize.svg import render_candidate_svg
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)


class TestGraphHelpers:
    def test_degree_components_has_edge(self):
        g = RoomGraph(room_ids=["a", "b", "c"])
        g.add_edge(
            RoomEdge(
                source_id="a", target_id="b", kind=RoomEdgeKind.ADJACENT, weight=1.0
            )
        )
        g.add_edge(
            RoomEdge(source_id="b", target_id="c", kind=RoomEdgeKind.NEAR, weight=0.5)
        )
        assert degree(g, "b") == 2
        assert has_edge(g, "a", "b", kind=RoomEdgeKind.ADJACENT)
        assert not has_edge(g, "a", "c")
        assert len(edges_for_room(g, "b")) == 2
        comps = connected_components(g, kinds={RoomEdgeKind.ADJACENT})
        # a-b 连通；c 单独（NEAR 未计入）
        sizes = sorted(len(c) for c in comps)
        assert sizes == [1, 2]


class TestSemanticRole:
    def test_semantic_role_beats_name(self):
        room = RoomSpec(
            id="r",
            name="随便叫",
            category=RoomCategory.PRIVATE,
            target_area=18,
            semantic_role=SemanticRole.MASTER_BEDROOM,
        )
        assert is_master_bedroom(room, allow_name_fallback=False)
        floors = [
            FloorSpec(id="F1", label="一层", room_ids=[]),
            FloorSpec(id="F2", label="二层", room_ids=[]),
        ]
        a = FloorAssignmentSolver().solve([room], floors)
        assert a.floor_id_for("r") == "F2"
        assert a.decision_for("r").rule_id == "master_bedroom.upper"


class TestEntryAndRoad:
    def test_preferred_edge_from_spec(self):
        site = SiteSpec(
            width=10,
            depth=10,
            entrance_edge=CardinalEdge.SOUTH,
            road_edges=[CardinalEdge.EAST],
        )
        program = DesignProgram(
            project_id="e",
            site=site,
            buildable=site.buildable_envelope,
            floors=[FloorSpec(id="F1", label="一层", room_ids=["living"])],
            rooms=[
                RoomSpec(
                    id="living",
                    name="客厅",
                    category=RoomCategory.PUBLIC,
                    target_area=20,
                    floor_id="F1",
                    semantic_role=SemanticRole.LIVING,
                )
            ],
            constraints=[],
            exterior_entry_spec=ExteriorEntrySpec(
                preferred_edge=CardinalEdge.EAST, width=1.5
            ),
            solver_config=SolverConfig(),
        )
        assert resolve_entry_edge(program) == CardinalEdge.EAST
        living = RoomPlacement(
            room_id="living",
            floor_id="F1",
            rect=PlacementRect(x=7, y=2, width=3, depth=6),
            source=PlacementSource.PROGRAM,
            category="public",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living])],
        )
        entry = resolve_exterior_entry(program, candidate)
        assert entry.edge == CardinalEdge.EAST
        assert entry.on_road_edge is True
        assert abs(entry.x - site.buildable_envelope.x1) < 1e-6 or entry.x >= 9.0

    def test_entry_and_garage_road_metrics(self):
        program = benchmark_program()
        program.site.road_edges = [program.site.entrance_edge]
        ensure_floor_assignment(program.rooms, program.floors, program.constraints)
        candidate = GuillotineGenerator().generate(program, seed=0)
        m = compute_site_metrics(program, candidate)
        assert "entry_on_road" in m
        assert "garage_on_road" in m
        assert candidate.exterior_entry is not None


class TestSvgDebugOverlays:
    def test_svg_shows_north_and_entry(self):
        program = benchmark_program()
        ensure_floor_assignment(program.rooms, program.floors, program.constraints)
        candidate = GuillotineGenerator().generate(program, seed=0)
        svg = render_candidate_svg(
            candidate,
            floor_width=program.buildable.width,
            floor_depth=program.buildable.depth,
            site=program.site,
        )
        assert "north_angle=" in svg
        assert ">N<" in svg or ">N</text>" in svg
        assert "ENTRY" in svg

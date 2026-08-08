"""住宅默认 AccessGraph 派生与软评价。"""

from __future__ import annotations

from packages.schema.constraints import AccessConstraint, ConstraintSource
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec, SemanticRole
from packages.schema.site import SiteSpec
from packages.schema.topology import AccessGraph, SpaceConnection, SpaceConnectionType
from solver.evaluation.access import compute_access_metrics
from solver.evaluation.score import CompositeEvaluator
from solver.generators.guillotine import GuillotineGenerator
from solver.program.floor_assignment import ensure_floor_assignment
from solver.tests.test_guillotine import benchmark_program
from solver.topology.derive_access import (
    derive_residential_access_graph,
    ensure_access_graph,
)
from solver.visualize.svg import render_candidate_svg


def _hub_program() -> DesignProgram:
    rooms = [
        RoomSpec(
            id="living",
            name="客厅",
            category=RoomCategory.PUBLIC,
            target_area=24,
            semantic_role=SemanticRole.LIVING,
        ),
        RoomSpec(
            id="bed1",
            name="次卧",
            category=RoomCategory.PRIVATE,
            target_area=12,
            semantic_role=SemanticRole.BEDROOM,
            tags=["bedroom"],
        ),
        RoomSpec(
            id="kitchen",
            name="厨房",
            category=RoomCategory.WET,
            target_area=8,
            semantic_role=SemanticRole.KITCHEN,
            tags=["kitchen"],
        ),
        RoomSpec(
            id="dining",
            name="餐厅",
            category=RoomCategory.PUBLIC,
            target_area=10,
            semantic_role=SemanticRole.DINING,
            tags=["dining"],
        ),
    ]
    floors = [
        FloorSpec(id="F1", label="一层", room_ids=[]),
        FloorSpec(id="F2", label="二层", room_ids=[]),
    ]
    site = SiteSpec(width=11, depth=13)
    program = DesignProgram(
        project_id="access-derive",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(candidate_count=4, return_top_k=2),
    )
    ensure_floor_assignment(program.rooms, program.floors, program.constraints)
    return program


class TestDeriveAccess:
    def test_living_bedroom_and_kitchen_dining_soft_edges(self):
        program = _hub_program()
        graph = derive_residential_access_graph(program)
        types = {(c.a, c.b, c.type, c.required) for c in graph.connections}
        # living↔bed door soft（楼层可能都在 F1 或分到上下）
        door_pairs = {
            frozenset((c.a, c.b))
            for c in graph.connections
            if c.type == SpaceConnectionType.DOOR and not c.required
        }
        open_pairs = {
            frozenset((c.a, c.b))
            for c in graph.connections
            if c.type == SpaceConnectionType.OPEN
        }
        # 同层才建边：floor assign 后 living+dining+kitchen 常在 F1，bed 可能 F2
        assert frozenset(("kitchen", "dining")) in open_pairs
        same_floor_as_living = {
            r.id
            for r in program.rooms
            if r.floor_id
            == next(x.floor_id for x in program.rooms if x.id == "living")
        }
        if "bed1" in same_floor_as_living:
            assert frozenset(("living", "bed1")) in door_pairs
        assert all(not t[3] for t in types if t[2] != SpaceConnectionType.EXTERIOR_ENTRY)

    def test_access_constraint_exterior_required(self):
        program = _hub_program()
        program.constraints.append(
            AccessConstraint(
                id="acc-living-ext",
                room_id="living",
                requires_exterior=True,
                hard=True,
                source=ConstraintSource.USER,
            )
        )
        graph = derive_residential_access_graph(program)
        ext = [
            c
            for c in graph.connections
            if c.type == SpaceConnectionType.EXTERIOR_ENTRY and c.b == "living"
        ]
        assert len(ext) == 1
        assert ext[0].required is True

    def test_ensure_fills_once_and_preserves_user(self):
        program = _hub_program()
        g1 = ensure_access_graph(program)
        assert program.access_graph is g1
        g2 = ensure_access_graph(program)
        assert g2 is g1

        custom = AccessGraph()
        custom.add_connection(
            SpaceConnection(
                id="user-door",
                a="living",
                b="bed1",
                type=SpaceConnectionType.DOOR,
                required=True,
            )
        )
        program.access_graph = custom
        assert ensure_access_graph(program) is custom

    def test_generator_fills_access_graph(self):
        program = benchmark_program()
        assert program.access_graph is None
        GuillotineGenerator().generate(program, seed=0)
        assert program.access_graph is not None
        assert len(program.access_graph.connections) >= 1

    def test_soft_metrics_and_circulation_score(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        m = compute_access_metrics(program, candidate)
        assert "access_pref_satisfaction" in m
        assert 0.0 <= m["access_pref_satisfaction"] <= 1.0
        score = CompositeEvaluator().evaluate(program, candidate)
        assert score.circulation_score >= 0.0

    def test_svg_draws_access_dashes(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        ensure_access_graph(program)
        svg = render_candidate_svg(
            candidate,
            floor_width=program.buildable.width,
            floor_depth=program.buildable.depth,
            site=program.site,
            access_graph=program.access_graph,
        )
        assert "access_edges=" in svg
        assert "stroke-dasharray" in svg

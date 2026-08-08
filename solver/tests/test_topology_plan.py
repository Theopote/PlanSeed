"""TopologyPlan — RoomGraph 驱动的生成前拓扑。"""

from __future__ import annotations

from packages.schema.constraints import (
    AdjacencyConstraint,
    ConstraintSource,
    SeparationConstraint,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.topology import RoomEdge, RoomEdgeKind, RoomGraph
from solver.evaluation.adjacency import compute_adjacency_metrics
from solver.generators.guillotine import GuillotineGenerator
from solver.program.floor_assignment import ensure_floor_assignment
from solver.topology.plan import TopologyPlanner, order_rooms_for_zone


def _tiny_program(*, with_adj: bool = True, with_avoid: bool = False) -> DesignProgram:
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
        RoomSpec(
            id="dining",
            name="餐厅",
            category=RoomCategory.PUBLIC,
            target_area=12,
            tags=["dining"],
        ),
        RoomSpec(
            id="kitchen",
            name="厨房",
            category=RoomCategory.WET,
            target_area=10,
            tags=["kitchen"],
        ),
        RoomSpec(id="bed", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
    ]
    floors = [
        FloorSpec(id="F1", label="一层", room_ids=[]),
        FloorSpec(id="F2", label="二层", room_ids=[]),
    ]
    constraints = []
    if with_adj:
        constraints.append(
            AdjacencyConstraint(
                id="adj-living-dining",
                room_a_id="living",
                room_b_id="dining",
                hard=False,
                weight=1.0,
                source=ConstraintSource.USER,
            )
        )
    if with_avoid:
        constraints.append(
            SeparationConstraint(
                id="sep-kitchen-bed",
                room_a_id="kitchen",
                room_b_id="bed",
                hard=False,
                weight=0.8,
                source=ConstraintSource.USER,
            )
        )
    site = SiteSpec(width=11, depth=13)
    program = DesignProgram(
        project_id="topo-test",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=constraints,
        solver_config=SolverConfig(candidate_count=4, return_top_k=2),
    )
    ensure_floor_assignment(program.rooms, program.floors, program.constraints)
    graph = RoomGraph(room_ids=[r.id for r in rooms])
    for c in constraints:
        if isinstance(c, AdjacencyConstraint):
            graph.add_edge(
                RoomEdge(
                    source_id=c.room_a_id,
                    target_id=c.room_b_id,
                    kind=RoomEdgeKind.ADJACENT,
                    weight=c.weight,
                )
            )
        elif isinstance(c, SeparationConstraint):
            graph.add_edge(
                RoomEdge(
                    source_id=c.room_a_id,
                    target_id=c.room_b_id,
                    kind=RoomEdgeKind.AVOID,
                    weight=c.weight,
                )
            )
    # wet near edges
    wet = [r.id for r in rooms if r.category == RoomCategory.WET]
    for i, a in enumerate(wet):
        for b in wet[i + 1 :]:
            graph.add_edge(
                RoomEdge(source_id=a, target_id=b, kind=RoomEdgeKind.NEAR, weight=0.5)
            )
    program.room_graph = graph
    return program


class TestTopologyPlanner:
    def test_adjacent_forms_cluster_and_prefer(self):
        program = _tiny_program(with_adj=True)
        plan = TopologyPlanner().plan(program)
        assert any(
            set(c.room_ids) >= {"dining", "living"} for c in plan.clusters
        )
        pairs = {(p.room_a_id, p.room_b_id) for p in plan.prefer_adjacent}
        assert ("dining", "living") in pairs or ("living", "dining") in pairs
        # pack order 确定性
        again = TopologyPlanner().plan(program)
        assert plan.pack_order_hint == again.pack_order_hint
        assert "F1" in plan.pack_order_hint
        assert set(plan.pack_order_hint["F1"]) >= {"living", "dining", "kitchen"}

    def test_avoid_pairs_recorded(self):
        program = _tiny_program(with_adj=False, with_avoid=True)
        plan = TopologyPlanner().plan(program)
        ids = {(p.room_a_id, p.room_b_id) for p in plan.avoid_pairs}
        assert ("bed", "kitchen") in ids or ("kitchen", "bed") in ids

    def test_order_rooms_for_zone_keeps_cluster_contiguous(self):
        ordered = order_rooms_for_zone(
            ["c", "a", "b", "d"],
            pack_order=["a", "b", "c", "d"],
            cluster_members=[{"a", "b"}],
        )
        # a,b 应连续
        i_a, i_b = ordered.index("a"), ordered.index("b")
        assert abs(i_a - i_b) == 1

    def test_cached_topology_plan_reused(self):
        program = _tiny_program()
        first = TopologyPlanner().plan(program)
        program.topology_plan = first
        second = TopologyPlanner().plan(program)
        assert second is first


class TestTopologyInfluencesGenerator:
    def test_adjacency_satisfaction_with_topology_order(self):
        program = _tiny_program(with_adj=True)
        candidate = GuillotineGenerator().generate(program, seed=7)
        metrics = compute_adjacency_metrics(program, candidate)
        # 同层公共区邻接；拓扑序应至少不破坏软邻接评估通路
        assert "preferred_adjacency_satisfaction" in metrics
        assert 0.0 <= metrics["preferred_adjacency_satisfaction"] <= 1.0

    def test_deterministic_with_same_seed(self):
        program = _tiny_program()
        a = GuillotineGenerator().generate(program, seed=3)
        b = GuillotineGenerator().generate(program, seed=3)
        assert a.model_dump() == b.model_dump()

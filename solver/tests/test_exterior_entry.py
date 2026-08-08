"""ExteriorEntry ≠ StairCore。"""

from __future__ import annotations

from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge, SiteSpec
from solver.circulation.exterior_entry import resolve_exterior_entry
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program
from solver.topology.access import ENTRY_NODE_ID, build_realized_access_graph


def _program() -> DesignProgram:
    site = SiteSpec(
        width=10,
        depth=10,
        entrance_edge=CardinalEdge.SOUTH,
        road_edges=[CardinalEdge.SOUTH],
    )
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12),
    ]
    floors = [FloorSpec(id="F1", label="一层", room_ids=["living", "bed"])]
    for r in rooms:
        r.floor_id = "F1"
    return DesignProgram(
        project_id="entry-test",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(),
    )


class TestExteriorEntry:
    def test_entry_prefers_living_not_stair(self):
        program = _program()
        living = RoomPlacement(
            room_id="living",
            floor_id="F1",
            rect=PlacementRect(x=0, y=7, width=6, depth=3),
            source=PlacementSource.PROGRAM,
            name="客厅",
            category="public",
        )
        stair = RoomPlacement(
            room_id="stair-F1",
            floor_id="F1",
            rect=PlacementRect(x=6, y=7, width=2, depth=3),
            source=PlacementSource.GENERATED,
            name="楼梯",
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=6, depth=7),
            source=PlacementSource.PROGRAM,
            name="卧室",
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, stair, bed])],
        )
        entry = resolve_exterior_entry(program, candidate)
        assert entry.id == ENTRY_NODE_ID
        assert entry.edge == CardinalEdge.SOUTH
        assert entry.on_road_edge is True
        assert entry.connected_room_ids[0] == "living"
        assert "stair-F1" in entry.connected_room_ids
        # AccessGraph 起点连 living，不把楼梯当首选
        graph = build_realized_access_graph(program, candidate)
        ext = [
            c
            for c in graph.connections
            if c.type.value == "exterior_entry" and ENTRY_NODE_ID in (c.a, c.b)
        ]
        assert any("living" in (c.a, c.b) for c in ext)
        assert not any(
            "stair-F1" in (c.a, c.b) for c in ext
        ), "有厅时不应把楼梯作为 ExteriorEntry 首达"

    def test_guillotine_stair_not_named_entrance(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        assert candidate.exterior_entry is not None
        assert candidate.exterior_entry.id == "exterior-entry"
        for fl in candidate.floors:
            for p in fl.placements:
                if p.room_id.startswith("stair-"):
                    assert p.name == "楼梯"
                    assert "入口" not in (p.name or "")

"""入口优先连门厅 — B5 入口组织。"""

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


def test_entry_prefers_foyer_over_other_public() -> None:
    site = SiteSpec(width=12, depth=10, entrance_edge=CardinalEdge.SOUTH)
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
        RoomSpec(id="entry", name="门厅", category=RoomCategory.PUBLIC, target_area=6),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12),
    ]
    for r in rooms:
        r.floor_id = "F1"
    program = DesignProgram(
        project_id="entry-foyer",
        site=site,
        buildable=site.buildable_envelope,
        floors=[FloorSpec(id="F1", label="一层", room_ids=[r.id for r in rooms])],
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(),
    )
    # 南边：门厅与客厅都贴南外墙
    placements = [
        RoomPlacement(
            room_id="entry",
            floor_id="F1",
            rect=PlacementRect(x=4, y=0, width=4, depth=3),
            source=PlacementSource.PROGRAM,
            name="门厅",
            category="public",
        ),
        RoomPlacement(
            room_id="living",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=4, depth=6),
            source=PlacementSource.PROGRAM,
            name="客厅",
            category="public",
        ),
        RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=8, y=0, width=4, depth=6),
            source=PlacementSource.PROGRAM,
            name="卧室",
            category="private",
        ),
    ]
    cand = LayoutCandidate(
        id="e",
        seed=0,
        floors=[FloorLayout(floor_id="F1", placements=placements)],
    )
    entry = resolve_exterior_entry(program, cand)
    assert entry.connected_room_ids[0] == "entry"

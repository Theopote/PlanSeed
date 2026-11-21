"""黑卫软交换：无外墙卫浴与贴外墙邻房互换矩形。"""

from __future__ import annotations

from packages.schema.layout import PlacementRect, PlacementSource, RoomPlacement
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.topology import AccessGraph
from solver.geometry.wet_exterior_repair import swap_black_baths_to_exterior


def _program() -> DesignProgram:
    rooms = [
        RoomSpec(id="bath", name="卫生间", category=RoomCategory.WET, target_area=4),
        RoomSpec(
            id="storage",
            name="储藏",
            category=RoomCategory.OTHER,
            target_area=4,
            tags=["storage"],
        ),
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
    ]
    for r in rooms:
        r.floor_id = "F1"
    site = SiteSpec(width=10, depth=8)
    return DesignProgram(
        project_id="wet-swap",
        site=site,
        buildable=site.buildable_envelope,
        floors=[FloorSpec(id="F1", label="一层", room_ids=[r.id for r in rooms])],
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(),
        access_graph=AccessGraph(),
    )


def test_swap_black_bath_with_exterior_storage() -> None:
    program = _program()
    placements = [
        RoomPlacement(
            room_id="bath",
            floor_id="F1",
            rect=PlacementRect(x=2, y=2, width=2, depth=2),
            source=PlacementSource.PROGRAM,
            name="卫生间",
            category="wet",
        ),
        RoomPlacement(
            room_id="storage",
            floor_id="F1",
            rect=PlacementRect(x=0, y=2, width=2, depth=2),
            source=PlacementSource.PROGRAM,
            name="储藏",
            category="other",
        ),
        RoomPlacement(
            room_id="living",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=10, depth=2),
            source=PlacementSource.PROGRAM,
            name="客厅",
            category="public",
        ),
    ]
    rooms_by_id = {r.id: r for r in program.rooms}
    out = swap_black_baths_to_exterior(
        placements, program=program, rooms_by_id=rooms_by_id
    )
    by_id = {p.room_id: p for p in out}
    assert abs(by_id["bath"].rect.x - 0.0) < 1e-6
    assert abs(by_id["storage"].rect.x - 2.0) < 1e-6

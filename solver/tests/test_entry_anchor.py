"""入口公区预放置 — 贴入口边。"""

from __future__ import annotations

from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge
from solver.circulation.entry_anchor import (
    preplace_entry_anchor_room,
    select_entry_anchor_room,
)
from solver.geometry.rect import Rect, from_placement


def test_select_prefers_foyer_over_living() -> None:
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
        RoomSpec(id="entry", name="门厅", category=RoomCategory.PUBLIC, target_area=8),
    ]
    assert select_entry_anchor_room(rooms).id == "entry"


def test_preplace_foyer_on_west_edge() -> None:
    rooms = [
        RoomSpec(id="entry", name="门厅", category=RoomCategory.PUBLIC, target_area=8),
        RoomSpec(id="garage", name="车库", category=RoomCategory.OTHER, target_area=18),
    ]
    for r in rooms:
        r.floor_id = "F1"
    footprint = Rect(x=0, y=0, width=14, depth=18)
    stair = Rect(x=12.2, y=6.9, width=1.8, depth=4.2)
    out = preplace_entry_anchor_room(
        rooms,
        footprint=footprint,
        occupied=[stair],
        model_edge=CardinalEdge.WEST,
    )
    assert "entry" in out
    rect = from_placement(out["entry"])
    assert abs(rect.left - 0.0) < 1e-6
    assert rect.area + 1e-9 >= rooms[0].resolved_min_area()


def test_preplace_skips_when_edge_blocked() -> None:
    rooms = [
        RoomSpec(id="entry", name="门厅", category=RoomCategory.PUBLIC, target_area=8),
    ]
    rooms[0].floor_id = "F1"
    footprint = Rect(x=0, y=0, width=10, depth=10)
    # 整条西边被占满
    wall = Rect(x=0, y=0, width=2, depth=10)
    out = preplace_entry_anchor_room(
        rooms,
        footprint=footprint,
        occupied=[wall],
        model_edge=CardinalEdge.WEST,
    )
    assert out == {}


def test_preplace_within_pack_regions_only() -> None:
    rooms = [
        RoomSpec(id="entry", name="门厅", category=RoomCategory.PUBLIC, target_area=8),
    ]
    rooms[0].floor_id = "F1"
    footprint = Rect(x=0, y=0, width=14, depth=18)
    # DAY 区仅南侧条带（仍贴西边）
    day = Rect(x=0, y=11.1, width=14, depth=6.9)
    out = preplace_entry_anchor_room(
        rooms,
        footprint=footprint,
        occupied=[],
        model_edge=CardinalEdge.WEST,
        pack_regions=[day],
    )
    assert "entry" in out
    rect = from_placement(out["entry"])
    assert abs(rect.left - 0.0) < 1e-6
    assert rect.y + 1e-6 >= day.y
    assert rect.bottom <= day.bottom + 1e-6

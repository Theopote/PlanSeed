"""入口边 DAY 区偏置 — ZonePlanner 把门厅区贴到入口 model 边。"""

from __future__ import annotations

import random

from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge
from packages.schema.zoning import ArchitecturalZone
from solver.geometry.rect import Rect
from solver.topology.zoning import ZonePlanner


def test_day_zone_pinned_to_west_entry() -> None:
    rooms = [
        RoomSpec(id="entry", name="门厅", category=RoomCategory.PUBLIC, target_area=8),
        RoomSpec(
            id="garage1",
            name="车库1",
            category=RoomCategory.OTHER,
            target_area=18,
            tags=["garage"],
        ),
        RoomSpec(
            id="garage2",
            name="车库2",
            category=RoomCategory.OTHER,
            target_area=18,
            tags=["garage"],
        ),
        RoomSpec(
            id="laundry",
            name="洗衣间",
            category=RoomCategory.WET,
            target_area=5,
            tags=["laundry"],
        ),
    ]
    for r in rooms:
        r.floor_id = "F1"
    planner = ZonePlanner()
    # width>depth → 沿 x 切，与西入口法向对齐
    zones = planner.plan_geometry(
        rooms=rooms,
        free_rects=[Rect(x=0, y=0, width=18, depth=14)],
        snap_module=0.3,
        rng=random.Random(0),
        floor_id="F1",
        entry_model_edge=CardinalEdge.WEST,
    )
    day = next(z for z in zones if z.zone == ArchitecturalZone.DAY)
    assert abs(day.rect.x - 0.0) < 1e-6
    assert "entry" in day.room_ids


def test_foyer_zone_pinned_to_south_entry() -> None:
    rooms = [
        RoomSpec(id="entry", name="门厅", category=RoomCategory.PUBLIC, target_area=6),
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=22),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=14),
        RoomSpec(id="bath", name="卫生间", category=RoomCategory.WET, target_area=4),
    ]
    for r in rooms:
        r.floor_id = "F1"
    planner = ZonePlanner()
    # depth>width → 沿 y 切，与南入口法向对齐
    zones = planner.plan_geometry(
        rooms=rooms,
        free_rects=[Rect(x=0, y=0, width=10, depth=16)],
        snap_module=0.3,
        rng=random.Random(1),
        floor_id="F1",
        entry_model_edge=CardinalEdge.SOUTH,
    )
    foyer_zone = next(z for z in zones if "entry" in z.room_ids)
    assert abs((foyer_zone.rect.y + foyer_zone.rect.depth) - 16.0) < 1e-6


def test_no_foyer_keeps_area_order() -> None:
    """无门厅时不因入口重排 DAY，避免 valid 回退。"""
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=22),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=14),
        RoomSpec(id="bath", name="卫生间", category=RoomCategory.WET, target_area=4),
    ]
    for r in rooms:
        r.floor_id = "F1"
    planner = ZonePlanner()
    zones = planner.plan_geometry(
        rooms=rooms,
        free_rects=[Rect(x=0, y=0, width=10, depth=16)],
        snap_module=0.3,
        rng=random.Random(1),
        floor_id="F1",
        entry_model_edge=CardinalEdge.SOUTH,
    )
    # 面积序：DAY(22) 先于 NIGHT/SERVICE → 低 y 侧
    day = next(z for z in zones if z.zone == ArchitecturalZone.DAY)
    assert abs(day.rect.y - 0.0) < 1e-6


def test_wet_zone_pinned_to_split_end_on_single_floor() -> None:
    """一层：客卫所在 SERVICE 贴切分端，避免夹心黑卫。"""
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=22),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=14),
        RoomSpec(id="bath", name="卫生间", category=RoomCategory.WET, target_area=4),
    ]
    for r in rooms:
        r.floor_id = "F1"
    planner = ZonePlanner()
    zones = planner.plan_geometry(
        rooms=rooms,
        free_rects=[Rect(x=0, y=0, width=10, depth=16)],
        snap_module=0.3,
        rng=random.Random(1),
        floor_id="F1",
        wet_exterior_ends=True,
    )
    service = next(z for z in zones if z.zone == ArchitecturalZone.SERVICE)
    # 垂直条带切分：SERVICE 应贴 y=0 或 y=16 一端
    top = abs(service.rect.y - 0.0) < 1e-6
    bottom = abs((service.rect.y + service.rect.depth) - 16.0) < 1e-6
    assert top or bottom
    assert "bath" in service.room_ids

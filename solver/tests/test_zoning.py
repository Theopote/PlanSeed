"""ZonePlanner / 重复楼层归属测试。"""

from __future__ import annotations

import random

import pytest

from packages.schema.constraints import ConstraintSource, FloorConstraint
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.zoning import ArchitecturalZone
from solver.geometry.rect import Rect
from solver.program.floor_assignment import (
    DuplicateRoomAssignmentError,
    FloorAssignmentSolver,
)
from solver.topology.zoning import ZonePlanner, zone_for_room
from solver.tests.test_guillotine import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.pipeline import run_pipeline


class TestDuplicateAssignment:
    def test_duplicate_room_ids_across_floors_raises(self):
        rooms = [
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
        ]
        floors = [
            FloorSpec(id="F1", label="一层", room_ids=["r1"]),
            FloorSpec(id="F2", label="二层", room_ids=["r1"]),
        ]
        with pytest.raises(DuplicateRoomAssignmentError):
            FloorAssignmentSolver().solve(rooms, floors)

    def test_conflicting_explicit_sources_raise(self):
        rooms = [
            RoomSpec(
                id="r1",
                name="客厅",
                category=RoomCategory.PUBLIC,
                target_area=24,
                floor_id="F2",
            ),
        ]
        floors = [
            FloorSpec(id="F1", label="一层", room_ids=["r1"]),
            FloorSpec(id="F2", label="二层", room_ids=[]),
        ]
        with pytest.raises(DuplicateRoomAssignmentError):
            FloorAssignmentSolver().solve(rooms, floors)


class TestZonePlanner:
    def test_zone_mapping(self):
        assert zone_for_room(
            RoomSpec(id="a", name="客厅", category=RoomCategory.PUBLIC, target_area=24)
        ) == ArchitecturalZone.DAY
        assert zone_for_room(
            RoomSpec(id="b", name="主卧", category=RoomCategory.PRIVATE, target_area=18)
        ) == ArchitecturalZone.NIGHT
        assert zone_for_room(
            RoomSpec(id="c", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"])
        ) == ArchitecturalZone.SERVICE

    def test_group_and_plan_single_rect(self):
        rooms = [
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="r2", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="r3", name="卫生间", category=RoomCategory.WET, target_area=4),
        ]
        free = [Rect(x=0, y=0, width=10, depth=12)]
        plan = ZonePlanner().plan_floor(floor_id="F1", rooms=rooms, free_rects=free)
        zones = {z.zone for z in plan.zones}
        assert ArchitecturalZone.DAY in zones
        assert ArchitecturalZone.NIGHT in zones
        assert ArchitecturalZone.SERVICE in zones
        # 条带面积之和 ≈ 原矩形
        assert abs(sum(z.rect.area for z in plan.zones) - free[0].area) < 0.5

    def test_plan_building_shares_service_rect_across_floors(self):
        """F1 日区+服务、F2 夜区+服务 → SERVICE 几何必须一致。"""
        f1 = [
            RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="kitchen", name="厨房", category=RoomCategory.WET, target_area=10),
            RoomSpec(id="bath1", name="卫生间", category=RoomCategory.WET, target_area=4),
        ]
        f2 = [
            RoomSpec(id="bed", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="bath2", name="主卫", category=RoomCategory.WET, target_area=5),
        ]
        free = [Rect(x=0, y=0, width=10, depth=12)]
        plans = ZonePlanner().plan_building(
            floors=[("F1", f1), ("F2", f2)],
            free_rects=free,
            rng=random.Random(0),
        )
        s1 = next(z for z in plans["F1"].zones if z.zone == ArchitecturalZone.SERVICE)
        s2 = next(z for z in plans["F2"].zones if z.zone == ArchitecturalZone.SERVICE)
        assert s1.rect.x == pytest.approx(s2.rect.x)
        assert s1.rect.y == pytest.approx(s2.rect.y)
        assert s1.rect.width == pytest.approx(s2.rect.width)
        assert s1.rect.depth == pytest.approx(s2.rect.depth)
        assert set(s1.room_ids) == {"kitchen", "bath1"}
        assert set(s2.room_ids) == {"bath2"}
        # 空 zone 仍保留几何（本层无 night 房间的 F1 等）
        assert any(z.zone == ArchitecturalZone.NIGHT for z in plans["F1"].zones)

    def test_guillotine_uses_zones_and_still_places_all_rooms(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        placed = {
            p.room_id
            for fl in candidate.floors
            for p in fl.placements
            if p.source.value == "program"
        }
        assert placed == {r.id for r in program.rooms}

    def test_quality_still_holds_with_zones(self):
        program = benchmark_program()
        result = run_pipeline(program)
        assert result.valid / result.generated >= 0.70

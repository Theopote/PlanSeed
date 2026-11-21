"""ZonePlanner / 重复楼层归属测试。"""

from __future__ import annotations

import random

import pytest
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.zoning import ArchitecturalZone, WetStackGroup
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.rect import Rect
from solver.pipeline import run_pipeline
from solver.program.floor_assignment import (
    DuplicateRoomAssignmentError,
    FloorAssignmentSolver,
)
from solver.tests.quality_baselines import DEFAULT_QUALITY
from solver.tests.test_guillotine import benchmark_program
from solver.topology.zoning import (
    ZonePlanner,
    classify_room,
    wet_stack_group_for_room,
    zone_for_room,
)


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
    def test_functional_vs_wet_stack_mapping(self):
        kitchen = RoomSpec(
            id="c", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"]
        )
        assert zone_for_room(kitchen) == ArchitecturalZone.DAY
        assert wet_stack_group_for_room(kitchen) == WetStackGroup.WS1

        living = RoomSpec(id="a", name="客厅", category=RoomCategory.PUBLIC, target_area=24)
        assert zone_for_room(living) == ArchitecturalZone.DAY
        assert wet_stack_group_for_room(living) is None

        bed = RoomSpec(id="b", name="主卧", category=RoomCategory.PRIVATE, target_area=18)
        assert zone_for_room(bed) == ArchitecturalZone.NIGHT

        master = RoomSpec(
            id="d", name="主卫", category=RoomCategory.WET, target_area=5, tags=["ensuite"]
        )
        z = classify_room(master)
        assert z.functional_zone == ArchitecturalZone.NIGHT
        assert z.wet_stack_group == WetStackGroup.WS1

        guest = RoomSpec(id="e", name="公共卫生间", category=RoomCategory.WET, target_area=4)
        assert zone_for_room(guest) == ArchitecturalZone.SERVICE
        assert wet_stack_group_for_room(guest) == WetStackGroup.WS1

        garage = RoomSpec(
            id="g", name="车库/储藏", category=RoomCategory.OTHER, target_area=15, tags=["garage"]
        )
        assert zone_for_room(garage) == ArchitecturalZone.SERVICE
        assert wet_stack_group_for_room(garage) is None

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
        assert abs(sum(z.rect.area for z in plan.zones) - free[0].area) < 0.5

    def test_oversized_free_rect_does_not_starve_service(self):
        """南侧楼梯留下「一大两小」时，大块须切开，SERVICE 不得空仓。"""
        rooms = [
            RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=16),
            RoomSpec(
                id="kitchen",
                name="厨房",
                category=RoomCategory.WET,
                target_area=9,
                tags=["kitchen"],
            ),
            RoomSpec(id="bed1", name="主卧", category=RoomCategory.PRIVATE, target_area=12),
            RoomSpec(id="bed2", name="次卧", category=RoomCategory.PRIVATE, target_area=10),
            RoomSpec(id="bath1", name="卫生间", category=RoomCategory.WET, target_area=4),
        ]
        # 模拟 B01 seed=42：南侧楼梯扣完后的 free
        free = [
            Rect(x=0.0, y=0.0, width=8.0, depth=10.2),
            Rect(x=0.0, y=10.2, width=1.8, depth=1.8),
            Rect(x=6.0, y=10.2, width=2.0, depth=1.8),
        ]
        zones = ZonePlanner().plan_geometry(
            rooms=rooms,
            free_rects=free,
            snap_module=0.3,
            rng=random.Random(42),
            floor_id="F1",
        )
        by_zone = {z.zone for z in zones}
        assert ArchitecturalZone.SERVICE in by_zone
        service_area = sum(
            z.rect.width * z.rect.depth
            for z in zones
            if z.zone == ArchitecturalZone.SERVICE
        )
        assert service_area >= 3.0
        assert "bath1" in next(
            z.room_ids for z in zones if z.zone == ArchitecturalZone.SERVICE
        )

    def test_kitchen_packs_with_day_not_service_band(self):
        """厨房功能属 DAY；与客卫可同属 WS1，但不挤进 SERVICE 功能条。"""
        f1 = [
            RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(
                id="kitchen", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"]
            ),
            RoomSpec(id="bath1", name="卫生间", category=RoomCategory.WET, target_area=4),
        ]
        f2 = [
            RoomSpec(id="bed", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="bath2", name="公共卫生间", category=RoomCategory.WET, target_area=5),
        ]
        free = [Rect(x=0, y=0, width=10, depth=12)]
        building = ZonePlanner().plan_building(
            floors=[("F1", f1), ("F2", f2)],
            free_rects=free,
            rng=random.Random(0),
            max_wet_stacks=1,
        )
        # 整栋共享 WetStack 锚
        assert len(building.wet_stacks) == 1
        ws = building.wet_stacks[0]
        assert ws.id == "WS1"
        assert set(ws.floor_ids) == {"F1", "F2"}
        assert "kitchen" in ws.member_room_ids
        assert "bath1" in ws.member_room_ids

        plans = building.floors
        day_f1 = next(z for z in plans["F1"].zones if z.zone == ArchitecturalZone.DAY)
        assert "kitchen" in day_f1.room_ids
        assert "living" in day_f1.room_ids

        svc_f1 = next(z for z in plans["F1"].zones if z.zone == ArchitecturalZone.SERVICE)
        assert "bath1" in svc_f1.room_ids
        assert "kitchen" not in svc_f1.room_ids

        assert ArchitecturalZone.NIGHT not in {z.zone for z in plans["F1"].zones}
        assert ArchitecturalZone.NIGHT in {z.zone for z in plans["F2"].zones}

    def test_f1_rooms_fill_depth_after_reclaim(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        f1 = candidate.floors[0]
        living = next(p for p in f1.placements if p.name and "客厅" in p.name)
        assert living.rect.area >= 15.0
        bottoms = [
            p.rect.bottom for p in f1.placements if p.source.value == "program"
        ]
        assert max(bottoms) >= program.buildable.depth * 0.65

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
        ratio = result.valid / result.generated
        assert ratio >= DEFAULT_QUALITY.min_valid_ratio

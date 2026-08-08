"""楼层归属：防止程序房间凭空消失。"""

from __future__ import annotations

import pytest

from packages.schema.requirements import (
    RequirementSpec,
    SiteRequirements,
    SpaceRequirement,
)
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.project import ProjectSpec
from solver.generators.guillotine import GuillotineGenerator
from solver.program.floor_assign import (
    UnassignedRoomError,
    assert_all_rooms_placed,
    auto_assign_floor,
    ensure_floor_assignment,
)
from solver.program.normalize import normalize
from solver.program.requirements_normalize import normalize_requirements


class TestAutoAssignFloor:
    def test_never_returns_none_for_two_floors(self):
        for cat in RoomCategory:
            room = RoomSpec(id="x", name="测试", category=cat, target_area=10)
            assert auto_assign_floor(room, 2) in ("F1", "F2")

    def test_public_and_garage_on_ground(self):
        living = RoomSpec(id="l", name="客厅", category=RoomCategory.PUBLIC, target_area=24)
        garage = RoomSpec(
            id="g", name="车库", category=RoomCategory.OTHER, target_area=15, tags=["garage"]
        )
        assert auto_assign_floor(living, 2) == "F1"
        assert auto_assign_floor(garage, 2) == "F1"

    def test_bedroom_on_upper(self):
        bed = RoomSpec(id="b", name="主卧", category=RoomCategory.PRIVATE, target_area=18)
        assert auto_assign_floor(bed, 2) == "F2"


class TestEnsureFloorAssignment:
    def test_unassigned_rooms_get_floors(self):
        rooms = [
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="r2", name="餐厅", category=RoomCategory.PUBLIC, target_area=12),
            RoomSpec(id="r3", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"]),
            RoomSpec(id="r4", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="r5", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
            RoomSpec(id="r6", name="卫生间", category=RoomCategory.WET, target_area=4),
        ]
        floors = [
            FloorSpec(id="F1", label="一层", room_ids=[]),
            FloorSpec(id="F2", label="二层", room_ids=[]),
        ]
        newly = ensure_floor_assignment(rooms, floors)
        assert len(newly) == 6
        assert all(r.floor_id in ("F1", "F2") for r in rooms)
        covered = {rid for fl in floors for rid in fl.room_ids}
        assert covered == {r.id for r in rooms}
        assert "r1" in floors[0].room_ids
        assert "r4" in floors[1].room_ids

    def test_normalize_project_with_empty_floor_room_ids(self):
        """两层 + 无楼层声明 → normalize 后房间不得消失。"""
        spec = ProjectSpec(
            site=SiteSpec(width=11, depth=13),
            floors=[
                FloorSpec(id="F1", label="一层", room_ids=[]),
                FloorSpec(id="F2", label="二层", room_ids=[]),
            ],
            rooms=[
                RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
                RoomSpec(id="r2", name="餐厅", category=RoomCategory.PUBLIC, target_area=12),
                RoomSpec(id="r3", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"]),
                RoomSpec(id="r4", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
                RoomSpec(id="r5", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
                RoomSpec(id="r6", name="卫生间", category=RoomCategory.WET, target_area=4),
            ],
        )
        program = normalize(spec)
        assert program.unassigned_rooms() == []
        all_on_floors = {r.id for fl in program.floors for r in program.rooms_on_floor(fl.id)}
        assert all_on_floors == {r.id for r in program.rooms}

    def test_requirement_spaces_without_floor_preference(self):
        req = RequirementSpec(
            site=SiteRequirements(width=11, depth=13),
            floor_count=2,
            spaces=[
                SpaceRequirement(name="客厅", category="public", target_area=24),
                SpaceRequirement(name="餐厅", category="public", target_area=12),
                SpaceRequirement(name="厨房", category="wet", target_area=10, tags=["kitchen"]),
                SpaceRequirement(name="主卧", category="private", target_area=18),
                SpaceRequirement(name="次卧", category="private", target_area=12),
                SpaceRequirement(name="卫生间", category="wet", target_area=4),
            ],
        )
        program = normalize_requirements(req)
        assert program.unassigned_rooms() == []
        assert len(program.rooms) == 6
        on_f1 = {r.id for r in program.rooms_on_floor("F1")}
        on_f2 = {r.id for r in program.rooms_on_floor("F2")}
        assert on_f1 | on_f2 == {r.id for r in program.rooms}
        assert on_f1 & on_f2 == set()
        # 生成后 placement 含全部 program 房间 + generated stair
        candidate = GuillotineGenerator().generate(program, seed=0)
        program_ids = {r.id for r in program.rooms}
        placed = {
            p.room_id
            for fl in candidate.floors
            for p in fl.placements
            if p.source.value == "program"
        }
        assert placed == program_ids

    def test_assert_raises_when_rooms_missing(self):
        rooms = [RoomSpec(id="ghost", name="幽灵", category=RoomCategory.OTHER, target_area=10)]
        floors = [FloorSpec(id="F1", label="一层", room_ids=[])]
        with pytest.raises(UnassignedRoomError):
            assert_all_rooms_placed(rooms, floors)

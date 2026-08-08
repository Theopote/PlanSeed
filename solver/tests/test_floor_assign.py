"""FloorAssignmentSolver — 楼层归属独立求解。"""

from __future__ import annotations

from packages.schema.constraints import ConstraintSource, FloorConstraint
from packages.schema.floor_assignment import FloorAssignmentSource
from packages.schema.project import ProjectSpec
from packages.schema.requirements import (
    RequirementSpec,
    SiteRequirements,
    SpaceRequirement,
)
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from solver.generators.guillotine import GuillotineGenerator
from solver.program.floor_assignment import (
    FloorAssignmentSolver,
    UnassignedRoomError,
    assert_all_rooms_placed,
    ensure_floor_assignment,
)
from solver.program.normalize import normalize
from solver.program.requirements_normalize import normalize_requirements_to_program


def _two_empty_floors() -> list[FloorSpec]:
    return [
        FloorSpec(id="F1", label="一层", room_ids=[]),
        FloorSpec(id="F2", label="二层", room_ids=[]),
    ]


class TestFloorAssignmentSolver:
    def test_pipeline_covers_all_rooms(self):
        rooms = [
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="r2", name="餐厅", category=RoomCategory.PUBLIC, target_area=12, tags=["dining"]),
            RoomSpec(id="r3", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"]),
            RoomSpec(id="r4", name="主卧", category=RoomCategory.PRIVATE, target_area=18, tags=["master"]),
            RoomSpec(id="r5", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
            RoomSpec(id="r6", name="卫生间", category=RoomCategory.WET, target_area=4),
        ]
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve(rooms, floors)
        assert {d.room_id for d in assignment.decisions} == {r.id for r in rooms}
        assignment.apply(rooms, floors)
        assert {rid for fl in floors for rid in fl.room_ids} == {r.id for r in rooms}

    def test_public_kitchen_dining_garage_on_f1(self):
        rooms = [
            RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="dining", name="餐厅", category=RoomCategory.PUBLIC, target_area=12),
            RoomSpec(id="kitchen", name="厨房", category=RoomCategory.WET, target_area=10, tags=["kitchen"]),
            RoomSpec(id="garage", name="车库", category=RoomCategory.OTHER, target_area=15, tags=["garage"]),
        ]
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve(rooms, floors)
        for rid in ("living", "dining", "kitchen", "garage"):
            assert assignment.floor_id_for(rid) == "F1"

    def test_private_and_master_on_upper(self):
        rooms = [
            RoomSpec(id="master", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="bed2", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
        ]
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve(rooms, floors)
        assert assignment.floor_id_for("master") == "F2"
        assert assignment.floor_id_for("bed2") == "F2"
        d = assignment.decision_for("master")
        assert d is not None
        assert d.source == FloorAssignmentSource.RESIDENTIAL_RULE
        assert d.rule_id == "master_bedroom.upper"

    def test_elderly_bedroom_prefers_ground(self):
        room = RoomSpec(
            id="elder",
            name="老人房",
            category=RoomCategory.PRIVATE,
            target_area=14,
            tags=["elderly"],
        )
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve([room], floors)
        assert assignment.floor_id_for("elder") == "F1"
        assert assignment.decision_for("elder").rule_id == "elderly_bedroom.ground"

    def test_master_bath_follows_master(self):
        rooms = [
            RoomSpec(id="master", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="mbath", name="主卫", category=RoomCategory.WET, target_area=5),
        ]
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve(rooms, floors)
        assert assignment.floor_id_for("master") == "F2"
        assert assignment.floor_id_for("mbath") == "F2"
        assert assignment.decision_for("mbath").rule_id == "wet.master_bath_follows_master"

    def test_explicit_floor_constraint_wins(self):
        rooms = [
            RoomSpec(id="study", name="书房", category=RoomCategory.OTHER, target_area=9),
        ]
        floors = _two_empty_floors()
        constraints = [
            FloorConstraint(
                id="force-study-f1",
                room_id="study",
                floor_id="F1",
                source=ConstraintSource.USER,
                description="书房放一层",
            )
        ]
        assignment = FloorAssignmentSolver().solve(rooms, floors, constraints)
        assert assignment.floor_id_for("study") == "F1"
        assert assignment.decision_for("study").source == FloorAssignmentSource.EXPLICIT_CONSTRAINT

    def test_decisions_are_explainable(self):
        rooms = [
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
        ]
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve(rooms, floors)
        d = assignment.decision_for("r1")
        assert d is not None
        assert d.source_key is not None
        assert d.reason
        assert d.rule_id

    def test_normalize_attaches_floor_assignment(self):
        spec = ProjectSpec(
            site=SiteSpec(width=11, depth=13),
            floors=_two_empty_floors(),
            rooms=[
                RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
                RoomSpec(id="r2", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            ],
        )
        program = normalize(spec)
        assert program.floor_assignment is not None
        assert program.unassigned_rooms() == []
        assert len(program.floor_assignment.decisions) == 2

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
        program = normalize_requirements_to_program(req)
        assert program.unassigned_rooms() == []
        assert program.floor_assignment is not None
        on_f1 = {r.id for r in program.rooms_on_floor("F1")}
        on_f2 = {r.id for r in program.rooms_on_floor("F2")}
        assert on_f1 | on_f2 == {r.id for r in program.rooms}
        assert on_f1 & on_f2 == set()
        candidate = GuillotineGenerator().generate(program, seed=0)
        placed = {
            p.room_id
            for fl in candidate.floors
            for p in fl.placements
            if p.source.value == "program"
        }
        assert placed == {r.id for r in program.rooms}

    def test_tags_drive_rules_without_chinese_name(self):
        """Solver 读 tags；name 可为任意 UI 文案。"""
        rooms = [
            RoomSpec(
                id="parents",
                name="父母房",
                category=RoomCategory.PRIVATE,
                target_area=14,
                tags=["bedroom", "elderly_accessible"],
            ),
            RoomSpec(
                id="suite",
                name="套房",
                category=RoomCategory.PRIVATE,
                target_area=20,
                tags=["bedroom", "master"],
            ),
            RoomSpec(
                id="west_kitchen",
                name="西厨",
                category=RoomCategory.WET,
                target_area=8,
                tags=["kitchen"],
            ),
            RoomSpec(
                id="ensuite",
                name="套房卫浴",
                category=RoomCategory.WET,
                target_area=5,
                tags=["master_bath"],
            ),
        ]
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve(rooms, floors)
        assert assignment.floor_id_for("parents") == "F1"
        assert assignment.decision_for("parents").rule_id == "elderly_bedroom.ground"
        assert assignment.floor_id_for("suite") == "F2"
        assert assignment.decision_for("suite").rule_id == "master_bedroom.upper"
        assert assignment.floor_id_for("west_kitchen") == "F1"
        assert assignment.floor_id_for("ensuite") == "F2"
        assert assignment.decision_for("ensuite").rule_id == "wet.master_bath_follows_master"

    def test_parents_room_without_tags_is_not_elderly_by_name(self):
        """禁止靠「父母」子串推断；无 tags 时按普通 PRIVATE → 上层。"""
        room = RoomSpec(
            id="parents",
            name="父母房",
            category=RoomCategory.PRIVATE,
            target_area=14,
        )
        floors = _two_empty_floors()
        assignment = FloorAssignmentSolver().solve([room], floors)
        assert assignment.floor_id_for("parents") == "F2"
        assert assignment.decision_for("parents").rule_id == "private.upper"

    def test_assert_raises_when_rooms_missing(self):
        rooms = [RoomSpec(id="ghost", name="幽灵", category=RoomCategory.OTHER, target_area=10)]
        floors = [FloorSpec(id="F1", label="一层", room_ids=[])]
        import pytest

        with pytest.raises(UnassignedRoomError):
            assert_all_rooms_placed(rooms, floors)

    def test_generator_does_not_guess_floors(self):
        """Generator 只消费已写好的 floor.room_ids。"""
        rooms = [
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="r2", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
        ]
        floors = _two_empty_floors()
        assignment = ensure_floor_assignment(rooms, floors)
        assert assignment.floor_id_for("r1") == "F1"
        assert floors[0].room_ids == ["r1"]
        assert floors[1].room_ids == ["r2"]

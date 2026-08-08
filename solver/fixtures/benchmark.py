"""Demo / 回归用基准住宅 fixture — 非生产 normalizer 默认。"""

from __future__ import annotations

from packages.schema.program import DesignProgram
from packages.schema.project import ProjectSpec
from packages.schema.requirements import RequirementSpec, SiteRequirements, SpaceRequirement
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from solver.program.normalize import normalize


def benchmark_rooms_and_floors() -> tuple[list[RoomSpec], list[FloorSpec]]:
    rooms = [
        RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24, floor_id="F1"),
        RoomSpec(
            id="r2",
            name="餐厅+厨房",
            category=RoomCategory.WET,
            target_area=16,
            floor_id="F1",
            tags=["kitchen"],
        ),
        RoomSpec(id="r3", name="卫生间", category=RoomCategory.WET, target_area=4, floor_id="F1"),
        RoomSpec(
            id="r4",
            name="车库/储藏",
            category=RoomCategory.OTHER,
            target_area=15,
            floor_id="F1",
            tags=["garage"],
        ),
        RoomSpec(id="r5", name="主卧", category=RoomCategory.PRIVATE, target_area=18, floor_id="F2"),
        RoomSpec(
            id="r6",
            name="主卫",
            category=RoomCategory.WET,
            target_area=5,
            floor_id="F2",
            tags=["ensuite", "master_bath"],
        ),
        RoomSpec(id="r7", name="次卧1", category=RoomCategory.PRIVATE, target_area=12, floor_id="F2"),
        RoomSpec(id="r8", name="次卧2", category=RoomCategory.PRIVATE, target_area=12, floor_id="F2"),
        RoomSpec(id="r9", name="公共卫生间", category=RoomCategory.WET, target_area=4, floor_id="F2"),
        RoomSpec(id="r10", name="书房", category=RoomCategory.OTHER, target_area=9, floor_id="F2"),
    ]
    floors = [
        FloorSpec(id="F1", label="一层", room_ids=["r1", "r2", "r3", "r4"]),
        FloorSpec(id="F2", label="二层", room_ids=["r5", "r6", "r7", "r8", "r9", "r10"]),
    ]
    return rooms, floors


def benchmark_spaces() -> list[SpaceRequirement]:
    return [
        SpaceRequirement(id="r1", name="客厅", category="public", target_area=24, floor_preference=["F1"]),
        SpaceRequirement(
            id="r2",
            name="餐厅+厨房",
            category="wet",
            target_area=16,
            tags=["kitchen"],
            floor_preference=["F1"],
        ),
        SpaceRequirement(id="r3", name="卫生间", category="wet", target_area=4, floor_preference=["F1"]),
        SpaceRequirement(
            id="r4",
            name="车库/储藏",
            category="other",
            target_area=15,
            tags=["garage"],
            floor_preference=["F1"],
        ),
        SpaceRequirement(id="r5", name="主卧", category="private", target_area=18, floor_preference=["F2"]),
        SpaceRequirement(
            id="r6",
            name="主卫",
            category="wet",
            target_area=5,
            tags=["ensuite", "master_bath"],
            floor_preference=["F2"],
        ),
        SpaceRequirement(id="r7", name="次卧1", category="private", target_area=12, floor_preference=["F2"]),
        SpaceRequirement(id="r8", name="次卧2", category="private", target_area=12, floor_preference=["F2"]),
        SpaceRequirement(
            id="r9", name="公共卫生间", category="wet", target_area=4, floor_preference=["F2"]
        ),
        SpaceRequirement(id="r10", name="书房", category="other", target_area=9, floor_preference=["F2"]),
    ]


def benchmark_requirement_spec(
    *,
    width: float = 11.0,
    depth: float = 13.0,
) -> RequirementSpec:
    return RequirementSpec(
        site=SiteRequirements(width=width, depth=depth),
        floor_count=2,
        spaces=benchmark_spaces(),
    )


def benchmark_program() -> DesignProgram:
    rooms, floors = benchmark_rooms_and_floors()
    spec = ProjectSpec(
        site=SiteSpec(width=11, depth=13, stair_width=1.8, stair_depth=4.2),
        floors=floors,
        rooms=rooms,
    )
    return normalize(spec)

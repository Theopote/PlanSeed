"""RequirementSpec → DesignProgram 规范化（含住宅默认值）。"""

from __future__ import annotations

from packages.schema.constraints import (
    AdjacencyConstraint,
    AlignmentConstraint,
    AreaConstraint,
    ConstraintKind,
    ConstraintSource,
    OrientationConstraint,
    WidthConstraint,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.project import HouseholdSpec, PreferencesSpec, ProjectSpec
from packages.schema.requirements import RequirementSpec, SpaceRequirement
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SetbackSpec, SiteSpec
from packages.schema.topology import RoomEdge, RoomEdgeKind, RoomGraph
from solver.program.normalize import build_room_graph, normalize as normalize_project


# 住宅默认面积（平方米）— 来自 normalizer，非 LLM 猜测
DEFAULT_AREA_BY_TAG: dict[str, float] = {
    "living": 24.0,
    "kitchen": 12.0,
    "dining": 10.0,
    "bedroom": 12.0,
    "master_bedroom": 18.0,
    "bathroom": 4.0,
    "garage": 15.0,
    "study": 9.0,
}

DEFAULT_AREA_BY_CATEGORY: dict[RoomCategory, float] = {
    RoomCategory.PUBLIC: 24.0,
    RoomCategory.PRIVATE: 12.0,
    RoomCategory.WET: 4.0,
    RoomCategory.OTHER: 10.0,
}


def normalize_requirements(
    req: RequirementSpec,
    config: SolverConfig | None = None,
) -> DesignProgram:
    """RequirementSpec → ProjectSpec（内部）→ DesignProgram。"""
    project = _requirements_to_project(req)
    program = normalize_project(project, config)
    program.constraints = _apply_preference_constraints(req, program.constraints, program)
    program.room_graph = build_room_graph(project)
    return program


def _requirements_to_project(req: RequirementSpec) -> ProjectSpec:
    width = req.site.width or 11.0
    depth = req.site.depth or 13.0
    floor_count = req.floor_count or _infer_floor_count(req)

    site = SiteSpec(
        width=width,
        depth=depth,
        north_angle=req.site.north_angle or 0.0,
        entrance_edge=req.site.entrance_edge or "south",
        road_edges=req.site.road_edges,
        setbacks=req.site.setbacks or SetbackSpec(),
    )

    household = HouseholdSpec(
        occupants=req.household.occupants or 4,
        bedrooms=req.household.bedrooms or 3,
        bathrooms=req.household.bathrooms or 2,
        has_garage=req.household.has_garage if req.household.has_garage is not None else True,
        notes=req.household.notes,
    )

    rooms, floors = _spaces_to_rooms_and_floors(req.spaces, floor_count)

    preferences = PreferencesSpec(
        prefer_south_facing_living=req.preferences.prefer_south_facing_living or False,
        prefer_open_kitchen_dining=req.preferences.prefer_open_kitchen_dining or False,
        prefer_compact_footprint=req.preferences.prefer_compact_footprint or False,
        prefer_short_corridor=req.preferences.prefer_short_corridor or False,
        quiet_zone_away_from_entry=req.preferences.quiet_zone_away_from_entry or False,
    )

    return ProjectSpec(
        id="from-requirements",
        site=site,
        household=household,
        floors=floors,
        rooms=rooms,
        preferences=preferences,
    )


def _infer_floor_count(req: RequirementSpec) -> int:
    prefs = [s for s in req.spaces if s.floor_preference]
    if prefs:
        return min(3, max(len({f for s in prefs for f in s.floor_preference}), 1))
    return 2


def _spaces_to_rooms_and_floors(
    spaces: list[SpaceRequirement],
    floor_count: int,
) -> tuple[list[RoomSpec], list[FloorSpec]]:
    if not spaces:
        return _default_benchmark_rooms(floor_count)

    floors = [
        FloorSpec(id=f"F{i + 1}", label=f"{i + 1}层" if i == 0 else f"{i + 1}层", room_ids=[])
        for i in range(floor_count)
    ]
    floor_labels = ["一层", "二层", "三层"]
    for i, f in enumerate(floors):
        f.label = floor_labels[i] if i < len(floor_labels) else f"F{i + 1}"

    rooms: list[RoomSpec] = []
    for idx, space in enumerate(spaces):
        rid = space.id or f"r{idx + 1}"
        category = _parse_category(space.category, space.tags, space.name)
        target = space.target_area or _default_area(space, category)
        floor_id = space.floor_preference[0] if space.floor_preference else None

        room = RoomSpec(
            id=rid,
            name=space.name,
            category=category,
            target_area=target,
            min_width=space.min_width,
            floor_id=floor_id,
            floor_preference=space.floor_preference,
            preferred_orientation=space.preferred_orientation,
            tags=space.tags,
        )
        rooms.append(room)

        assigned = floor_id or _auto_assign_floor(rid, category, floor_count)
        if assigned:
            for fl in floors:
                if fl.id == assigned:
                    fl.room_ids.append(rid)

    for fl in floors:
        if not fl.room_ids:
            fl.room_ids = [r.id for r in rooms if r.floor_id == fl.id or fl.id in r.floor_preference]

    return rooms, floors


def _parse_category(raw: str | None, tags: list[str], name: str) -> RoomCategory:
    if raw:
        try:
            return RoomCategory(raw)
        except ValueError:
            pass
    name_l = name.lower()
    if any(t in tags for t in ("kitchen", "bathroom", "wet")) or "卫" in name or "厨" in name:
        return RoomCategory.WET
    if "卧" in name or "bedroom" in tags:
        return RoomCategory.PRIVATE
    if "客厅" in name or "living" in tags:
        return RoomCategory.PUBLIC
    if "车库" in name or "garage" in tags:
        return RoomCategory.OTHER
    return RoomCategory.OTHER


def _default_area(space: SpaceRequirement, category: RoomCategory) -> float:
    for tag in space.tags:
        if tag in DEFAULT_AREA_BY_TAG:
            return DEFAULT_AREA_BY_TAG[tag]
    return DEFAULT_AREA_BY_CATEGORY.get(category, 10.0)


def _auto_assign_floor(rid: str, category: RoomCategory, floor_count: int) -> str | None:
    if floor_count == 1:
        return "F1"
    return None


def _default_benchmark_rooms(floor_count: int) -> tuple[list[RoomSpec], list[FloorSpec]]:
    """旧手册基准案例 — 用于 demo 与回归测试。"""
    rooms = [
        RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24, floor_id="F1"),
        RoomSpec(id="r2", name="餐厅+厨房", category=RoomCategory.WET, target_area=16, floor_id="F1", tags=["kitchen"]),
        RoomSpec(id="r3", name="卫生间", category=RoomCategory.WET, target_area=4, floor_id="F1"),
        RoomSpec(id="r4", name="车库/储藏", category=RoomCategory.OTHER, target_area=15, floor_id="F1", tags=["garage"]),
        RoomSpec(id="r5", name="主卧", category=RoomCategory.PRIVATE, target_area=18, floor_id="F2"),
        RoomSpec(id="r6", name="主卫", category=RoomCategory.WET, target_area=5, floor_id="F2"),
        RoomSpec(id="r7", name="次卧1", category=RoomCategory.PRIVATE, target_area=12, floor_id="F2"),
        RoomSpec(id="r8", name="次卧2", category=RoomCategory.PRIVATE, target_area=12, floor_id="F2"),
        RoomSpec(id="r9", name="公共卫生间", category=RoomCategory.WET, target_area=4, floor_id="F2"),
        RoomSpec(id="r10", name="书房", category=RoomCategory.OTHER, target_area=9, floor_id="F2"),
    ]
    floors = [
        FloorSpec(id="F1", label="一层", room_ids=["r1", "r2", "r3", "r4"]),
        FloorSpec(id="F2", label="二层", room_ids=["r5", "r6", "r7", "r8", "r9", "r10"]),
    ]
    return rooms[:], floors[:floor_count]


def _apply_preference_constraints(req, constraints: list, program: DesignProgram) -> list:
    merged = list(constraints)

    if req.preferences.prefer_south_facing_living:
        living = _find_room(program, names=["客厅", "living"])
        if living:
            merged.append(
                OrientationConstraint(
                    id="pref-living-south",
                    room_id=living.id,
                    preferred_orientation="south",
                    hard=False,
                    weight=0.8,
                    source=ConstraintSource.NORMALIZER,
                    source_key="preferences.prefer_south_facing_living",
                    description="客厅优先朝南",
                )
            )

    if req.preferences.wet_stack_preference:
        merged.append(
            AlignmentConstraint(
                id="pref-wet-stack",
                alignment_group="wet_zone",
                hard=False,
                weight=0.9,
                source=ConstraintSource.NORMALIZER,
                source_key="preferences.wet_stack_preference",
                description="湿区竖向叠置偏好",
            )
        )

    return merged


def _find_room(program: DesignProgram, names: list[str]) -> RoomSpec | None:
    for room in program.rooms:
        if any(n in room.name for n in names):
            return room
    return None

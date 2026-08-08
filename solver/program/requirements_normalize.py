"""RequirementSpec → DesignProgram 规范化（可解释 defaults / unknowns）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.constraints import (
    AlignmentConstraint,
    ConstraintSource,
    OrientationConstraint,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.project import HouseholdSpec, PreferencesSpec, ProjectSpec
from packages.schema.requirements import (
    Assumption,
    RequirementSpec,
    SpaceRequirement,
    UnknownRequirement,
)
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge, SetbackSpec, SiteSpec
from solver.program.floor_assign import ensure_floor_assignment
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

# 住户程序默认 — 必须写入 assumptions
DEFAULT_OCCUPANTS = 4
DEFAULT_BEDROOMS = 3
DEFAULT_BATHROOMS = 2
DEFAULT_HAS_GARAGE = True
DEFAULT_FLOOR_COUNT = 2


class IncompleteRequirementsError(ValueError):
    """存在阻塞求解的 unknowns（如未提供地块尺寸）。"""

    def __init__(self, unknowns: list[UnknownRequirement], message: str | None = None):
        self.unknowns = unknowns
        keys = ", ".join(u.key for u in unknowns)
        super().__init__(message or f"需求不完整，缺少: {keys}")


class RequirementsNormalizeResult(BaseModel):
    """规范化结果：始终带回可解释的 assumptions / unknowns。"""

    requirements: RequirementSpec
    program: DesignProgram | None = None
    can_solve: bool = False
    assumptions: list[Assumption] = Field(default_factory=list)
    unknowns: list[UnknownRequirement] = Field(default_factory=list)


def normalize_requirements(
    req: RequirementSpec,
    config: SolverConfig | None = None,
    *,
    require_complete: bool = True,
) -> RequirementsNormalizeResult:
    """
    RequirementSpec →（可选）DesignProgram。

    - 应用的默认值必须写入 assumptions
    - 地块 width/depth 缺失 → unknowns，不凭空填 11×13
    - require_complete=True 且存在阻塞 unknowns 时 program=None
    """
    working = req.model_copy(deep=True)
    assumptions: list[Assumption] = list(working.assumptions)
    unknowns: list[UnknownRequirement] = list(working.unknowns)

    def assume(key: str, value: str | int | float | bool, reason: str) -> None:
        if any(a.key == key for a in assumptions):
            return
        assumptions.append(Assumption(key=key, value=value, reason=reason))

    def mark_unknown(key: str, description: str) -> None:
        if any(u.key == key for u in unknowns):
            return
        unknowns.append(UnknownRequirement(key=key, description=description))

    # --- Site：尺寸不可静默默认 ---
    site_blocking: list[UnknownRequirement] = []
    if working.site.width is None:
        u = UnknownRequirement(key="site.width", description="未提供用地宽度，无法确定可建范围")
        site_blocking.append(u)
        mark_unknown(u.key, u.description)
    if working.site.depth is None:
        u = UnknownRequirement(key="site.depth", description="未提供用地深度，无法确定可建范围")
        site_blocking.append(u)
        mark_unknown(u.key, u.description)

    if working.site.north_angle is None:
        working.site.north_angle = 0.0
        assume("site.north_angle", 0.0, "未指定正北角度，默认与坐标系 Y 轴对齐")
    if working.site.entrance_edge is None:
        working.site.entrance_edge = CardinalEdge.SOUTH
        assume("site.entrance_edge", "south", "未指定主入口边，默认南侧入口")
    if working.site.setbacks is None:
        working.site.setbacks = SetbackSpec()
        assume(
            "site.setbacks",
            "0,0,0,0",
            "未提供退界，保持 0（表示未提供规划信息，非法规结论）",
        )

    # --- Floor count ---
    if working.floor_count is None:
        inferred = _infer_floor_count_from_spaces(working)
        working.floor_count = inferred
        assume(
            "floor_count",
            inferred,
            "未指定层数，根据空间偏好推断" if inferred != DEFAULT_FLOOR_COUNT else "未指定层数，应用住宅默认两层",
        )

    # --- Household ---
    hh = working.household
    if hh.occupants is None:
        hh.occupants = DEFAULT_OCCUPANTS
        assume(
            "household.occupants",
            DEFAULT_OCCUPANTS,
            "未指定居住人数，应用住宅默认程序",
        )
    if hh.bedrooms is None:
        hh.bedrooms = DEFAULT_BEDROOMS
        assume(
            "household.bedrooms",
            DEFAULT_BEDROOMS,
            "未指定卧室数量，应用住宅默认程序",
        )
    if hh.bathrooms is None:
        hh.bathrooms = DEFAULT_BATHROOMS
        assume(
            "household.bathrooms",
            DEFAULT_BATHROOMS,
            "未指定卫生间数量，应用住宅默认程序",
        )
    if hh.has_garage is None:
        hh.has_garage = DEFAULT_HAS_GARAGE
        assume(
            "household.has_garage",
            DEFAULT_HAS_GARAGE,
            "未指定是否需要车库，应用住宅默认程序（含车库）",
        )

    working.assumptions = assumptions
    working.unknowns = unknowns

    if site_blocking:
        if require_complete:
            return RequirementsNormalizeResult(
                requirements=working,
                program=None,
                can_solve=False,
                assumptions=assumptions,
                unknowns=unknowns,
            )
        # 不完整时仍可返回 trace，但不建 program
        return RequirementsNormalizeResult(
            requirements=working,
            program=None,
            can_solve=False,
            assumptions=assumptions,
            unknowns=unknowns,
        )

    assert working.site.width is not None and working.site.depth is not None
    assert working.floor_count is not None

    rooms, floors, space_assumptions = _spaces_to_rooms_and_floors(
        working.spaces, working.floor_count
    )
    for a in space_assumptions:
        assume(a.key, a.value, a.reason)

    working.assumptions = assumptions

    site = SiteSpec(
        width=working.site.width,
        depth=working.site.depth,
        north_angle=working.site.north_angle or 0.0,
        entrance_edge=working.site.entrance_edge or CardinalEdge.SOUTH,
        road_edges=working.site.road_edges,
        setbacks=working.site.setbacks or SetbackSpec(),
    )

    household = HouseholdSpec(
        occupants=hh.occupants or DEFAULT_OCCUPANTS,
        bedrooms=hh.bedrooms or DEFAULT_BEDROOMS,
        bathrooms=hh.bathrooms or DEFAULT_BATHROOMS,
        has_garage=hh.has_garage if hh.has_garage is not None else DEFAULT_HAS_GARAGE,
        notes=hh.notes,
    )

    prefs = working.preferences
    preferences = PreferencesSpec(
        prefer_south_facing_living=prefs.prefer_south_facing_living or False,
        prefer_open_kitchen_dining=prefs.prefer_open_kitchen_dining or False,
        prefer_compact_footprint=prefs.prefer_compact_footprint or False,
        prefer_short_corridor=prefs.prefer_short_corridor
        if prefs.prefer_short_corridor is not None
        else True,
        quiet_zone_away_from_entry=prefs.quiet_zone_away_from_entry
        if prefs.quiet_zone_away_from_entry is not None
        else True,
    )

    project = ProjectSpec(
        id="from-requirements",
        site=site,
        household=household,
        floors=floors,
        rooms=rooms,
        preferences=preferences,
    )

    program = normalize_project(project, config)
    program.constraints = _apply_preference_constraints(working, program.constraints, program)
    program.room_graph = build_room_graph(project)
    program.assumptions = list(assumptions)
    program.unknowns = list(unknowns)

    return RequirementsNormalizeResult(
        requirements=working,
        program=program,
        can_solve=True,
        assumptions=assumptions,
        unknowns=unknowns,
    )


def normalize_requirements_to_program(
    req: RequirementSpec,
    config: SolverConfig | None = None,
) -> DesignProgram:
    """需要 DesignProgram 的调用方；地块缺失时抛 IncompleteRequirementsError。"""
    result = normalize_requirements(req, config, require_complete=True)
    if result.program is None:
        blocking = [u for u in result.unknowns if u.key.startswith("site.")]
        raise IncompleteRequirementsError(blocking or result.unknowns)
    return result.program


def _infer_floor_count_from_spaces(req: RequirementSpec) -> int:
    prefs = [s for s in req.spaces if s.floor_preference]
    if prefs:
        return min(3, max(len({f for s in prefs for f in s.floor_preference}), 1))
    return DEFAULT_FLOOR_COUNT


def _spaces_to_rooms_and_floors(
    spaces: list[SpaceRequirement],
    floor_count: int,
) -> tuple[list[RoomSpec], list[FloorSpec], list[Assumption]]:
    assumptions: list[Assumption] = []

    if not spaces:
        rooms, floors = _default_benchmark_rooms(floor_count)
        assumptions.append(
            Assumption(
                key="spaces.program",
                value="benchmark_default",
                reason="未提供空间清单，应用基准住宅程序（演示/回归用）",
            )
        )
        return rooms, floors, assumptions

    floors = [
        FloorSpec(id=f"F{i + 1}", label=f"{i + 1}层", room_ids=[])
        for i in range(floor_count)
    ]
    floor_labels = ["一层", "二层", "三层"]
    for i, f in enumerate(floors):
        f.label = floor_labels[i] if i < len(floor_labels) else f"F{i + 1}"

    rooms: list[RoomSpec] = []
    for idx, space in enumerate(spaces):
        rid = space.id or f"r{idx + 1}"
        category = _parse_category(space.category, space.tags, space.name)
        if space.target_area is None:
            target = _default_area(space, category)
            assumptions.append(
                Assumption(
                    key=f"spaces.{rid}.target_area",
                    value=target,
                    reason=f"未指定「{space.name}」面积，应用住宅默认程序面积",
                )
            )
        else:
            target = space.target_area
        floor_id = space.floor_preference[0] if space.floor_preference else None

        rooms.append(
            RoomSpec(
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
        )

    ensure_floor_assignment(rooms, floors)
    return rooms, floors, assumptions


def _parse_category(raw: str | None, tags: list[str], name: str) -> RoomCategory:
    if raw:
        try:
            return RoomCategory(raw)
        except ValueError:
            pass
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

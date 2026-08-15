"""ADR-010 — STAIR / ATRIUM 预扣除放置。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from packages.schema.core import CorePlacement, CorePlacementResult, StairCoreSpec
from packages.schema.layout import PlacementRect
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.vertical_void import (
    VerticalVoidPlacement,
    VerticalVoidSpec,
    VerticalVoidType,
    void_covers_floor,
)

from solver.circulation.stair_core import (
    CorePlacementFailure,
    choose_core_placement,
    core_fits,
    core_from_locked_rect,
    default_orientation_for,
    place_stair_core,
    place_stair_core_resolving,
    resolve_stair_core_spec,
)
from solver.geometry.rect import Rect, from_placement, intersects


@dataclass
class PredeductionPlan:
    """跨层预扣除 void 的几何计划。"""

    stair_core: CorePlacementResult
    void_placements: list[VerticalVoidPlacement] = field(default_factory=list)
    holes_by_floor: dict[str, list[Rect]] = field(default_factory=dict)

    def atrium_placements_on_floor(self, floor_id: str) -> list[VerticalVoidPlacement]:
        return [
            vp
            for vp in self.void_placements
            if vp.floor_id == floor_id and vp.void_type == VerticalVoidType.ATRIUM
        ]


def stair_void_from_program(program: DesignProgram) -> VerticalVoidSpec | None:
    for spec in program.vertical_voids:
        if spec.void_type == VerticalVoidType.STAIR:
            return spec
    return None


def atrium_voids_from_program(program: DesignProgram) -> list[VerticalVoidSpec]:
    return [v for v in program.vertical_voids if v.void_type == VerticalVoidType.ATRIUM]


def resolve_stair_core_spec_for_program(program: DesignProgram) -> StairCoreSpec:
    """合并 VerticalVoidSpec(STAIR) 与 SiteSpec 楼梯尺寸。"""
    stair_void = stair_void_from_program(program)
    if stair_void is None:
        return resolve_stair_core_spec(
            stair_width=program.site.stair_width,
            stair_depth=getattr(program.site, "stair_depth", 4.2),
        )
    default = resolve_stair_core_spec()
    return StairCoreSpec(
        width=stair_void.width
        if stair_void.width is not None
        else (program.site.stair_width if program.site.stair_width is not None else default.width),
        depth=stair_void.depth
        if stair_void.depth is not None
        else getattr(program.site, "stair_depth", default.depth),
        preferred_placement=stair_void.preferred_placement,
    )


def _rect_overlaps_obstacles(rect: Rect, obstacles: list[Rect]) -> bool:
    return any(intersects(rect, obs) for obs in obstacles)


def _place_rect_avoiding_obstacles(
    *,
    floor_width: float,
    floor_depth: float,
    width: float,
    depth: float,
    preferred: CorePlacement | None,
    entrance_edge,
    snap_module: float,
    rng: random.Random,
    obstacles: list[Rect],
) -> PlacementRect:
    """在 footprint 内放置矩形，避开已有预扣除区域。"""
    spec = StairCoreSpec(width=width, depth=depth, preferred_placement=preferred)
    primary = choose_core_placement(
        rng,
        preferred=preferred,
        entrance_edge=entrance_edge,
    )
    placements_to_try = [primary, *[p for p in CorePlacement if p != primary]]
    attempts: list[tuple[CorePlacement, str]] = []
    for placement in placements_to_try:
        orient = default_orientation_for(placement)
        alt: str = "ew" if orient == "ns" else "ns"
        attempts.append((placement, orient))
        attempts.append((placement, alt))

    last_err: CorePlacementFailure | None = None
    for placement, orient in attempts:
        if not core_fits(
            floor_width=floor_width,
            floor_depth=floor_depth,
            spec=spec,
            orientation=orient,  # type: ignore[arg-type]
        ):
            continue
        try:
            result = place_stair_core(
                floor_width=floor_width,
                floor_depth=floor_depth,
                spec=spec,
                placement=placement,
                snap_module=snap_module,
                orientation=orient,  # type: ignore[arg-type]
            )
        except CorePlacementFailure as err:
            last_err = err
            continue
        rect = from_placement(result.rect)
        if _rect_overlaps_obstacles(rect, obstacles):
            continue
        return result.rect

    raise CorePlacementFailure(
        f"无法以 {width}×{depth} 放置竖向空洞（避开 {len(obstacles)} 个障碍）",
        spec=spec,
        floor_width=floor_width,
        floor_depth=floor_depth,
    ) from last_err


def build_prededuction_plan(
    program: DesignProgram,
    *,
    floor_width: float,
    floor_depth: float,
    snap_module: float,
    rng: random.Random,
    locks: LayoutLocks | None = None,
) -> PredeductionPlan:
    """
    解析 STAIR + ATRIUM void，产出跨层对齐的预扣除几何。

    无 vertical_voids 时行为与旧版隐式楼梯核一致。
    """
    locks = locks or LayoutLocks()
    floor_ids = [f.id for f in program.floors]
    stair_void = stair_void_from_program(program)
    atrium_voids = atrium_voids_from_program(program)
    core_spec = resolve_stair_core_spec_for_program(program)

    if locks.stair is not None:
        stair_core = core_from_locked_rect(
            x=locks.stair.x,
            y=locks.stair.y,
            width=locks.stair.width,
            depth=locks.stair.depth,
            core_placement=locks.stair.core_placement,
        )
    else:
        preferred = core_spec.preferred_placement
        if stair_void is not None and stair_void.preferred_placement is not None:
            preferred = stair_void.preferred_placement
        placement = choose_core_placement(
            rng,
            preferred=preferred,
            entrance_edge=program.site.entrance_edge,
        )
        stair_core = place_stair_core_resolving(
            floor_width=floor_width,
            floor_depth=floor_depth,
            spec=core_spec,
            primary_placement=placement,
            snap_module=snap_module,
            rng=rng,
        )

    stair_rect = from_placement(stair_core.rect)
    obstacles: list[Rect] = [stair_rect]
    void_placements: list[VerticalVoidPlacement] = []

    for atrium in atrium_voids:
        assert atrium.width is not None and atrium.depth is not None
        rect = _place_rect_avoiding_obstacles(
            floor_width=floor_width,
            floor_depth=floor_depth,
            width=atrium.width,
            depth=atrium.depth,
            preferred=atrium.preferred_placement,
            entrance_edge=program.site.entrance_edge,
            snap_module=snap_module,
            rng=rng,
            obstacles=obstacles,
        )
        atrium_rect = from_placement(rect)
        obstacles.append(atrium_rect)
        for floor_id in floor_ids:
            if not void_covers_floor(atrium, floor_id, floor_ids=floor_ids):
                continue
            void_placements.append(
                VerticalVoidPlacement(
                    void_id=atrium.id,
                    void_type=VerticalVoidType.ATRIUM,
                    floor_id=floor_id,
                    rect=rect.model_copy(),
                    skylight_required=atrium.skylight_required,
                )
            )

    holes_by_floor: dict[str, list[Rect]] = {}
    for floor_id in floor_ids:
        holes = [stair_rect]
        for vp in void_placements:
            if vp.floor_id == floor_id:
                holes.append(from_placement(vp.rect))
        holes_by_floor[floor_id] = holes

    return PredeductionPlan(
        stair_core=stair_core,
        void_placements=void_placements,
        holes_by_floor=holes_by_floor,
    )

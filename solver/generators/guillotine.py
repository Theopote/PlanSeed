"""Guillotine 递归切分 — ZonePlanner 之后的 RoomLayout strategy。"""

from __future__ import annotations

import random
from dataclasses import dataclass

from packages.schema.core import CorePlacementResult
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
    WetStack,
)
from packages.schema.program import DesignProgram
from packages.schema.room import RoomSpec
from packages.schema.zoning import ArchitecturalZone, FloorZonePlan
from solver.circulation.stair_core import (
    CorePlacementFailure,
    choose_core_placement,
    place_stair_core_resolving,
    resolve_stair_core_spec,
)
from solver.geometry.free_rects import subtract_rect
from solver.geometry.rect import Rect
from solver.geometry.snap import snap_value
from solver.program.floor_assign import assert_all_rooms_placed
from solver.topology.zoning import ZonePlanner


def _mirror_wet_stack_onto_floor(
    floor: FloorLayout, stack: WetStack | None
) -> FloorLayout:
    """兼容：主 WetStack 锚回填到 deprecated wet_zone_*。"""
    if stack is None:
        return floor
    a = stack.anchor_rect
    return floor.model_copy(
        update={
            "wet_zone_x0": a.x,
            "wet_zone_y0": a.y,
            "wet_zone_x1": a.x + a.width,
            "wet_zone_y1": a.y + a.depth,
        }
    )


@dataclass
class _LayoutRoom:
    spec: RoomSpec
    weight: float
    rect: PlacementRect | None = None


class GuillotineGenerator:
    """
    Generator #1 — Baseline Guillotine（RoomLayout strategy）。

    流水线：
      StairCore → free rects → ZonePlanner(功能区 + 技术湿区条带) → Guillotine
    """

    def __init__(self) -> None:
        self._zone_planner = ZonePlanner()

    def generate(self, program: DesignProgram, seed: int) -> LayoutCandidate:
        assert_all_rooms_placed(program.rooms, program.floors)
        rng = random.Random(seed)
        module = program.solver_config.snap_module
        buildable = program.buildable
        w = buildable.width
        d = buildable.depth

        core_spec = resolve_stair_core_spec(
            stair_width=program.site.stair_width,
            stair_depth=getattr(program.site, "stair_depth", 4.2),
        )
        placement = choose_core_placement(
            rng,
            preferred=core_spec.preferred_placement,
            entrance_edge=program.site.entrance_edge,
        )
        try:
            core = place_stair_core_resolving(
                floor_width=w,
                floor_depth=d,
                spec=core_spec,
                primary_placement=placement,
                snap_module=module,
                rng=rng,
            )
        except CorePlacementFailure as err:
            return LayoutCandidate(
                id=f"candidate-{seed}",
                seed=seed,
                floors=[FloorLayout(floor_id=fl.id, placements=[]) for fl in program.floors],
                metrics={
                    "core_unfit": True,
                    "core_unfit_reason": str(err),
                },
            )

        floor_rect = Rect(x=0, y=0, width=w, depth=d)
        core_rect = Rect(
            x=core.rect.x, y=core.rect.y, width=core.rect.width, depth=core.rect.depth
        )
        free_rects = subtract_rect(floor_rect, core_rect)

        floor_room_lists = [
            (floor.id, program.rooms_on_floor(floor.id)) for floor in program.floors
        ]
        building_zones = self._zone_planner.plan_building(
            floors=floor_room_lists,
            free_rects=free_rects,
            snap_module=module,
            rng=rng,
            max_wet_stacks=program.solver_config.max_wet_stacks,
        )
        primary_stack = building_zones.wet_stacks[0] if building_zones.wet_stacks else None

        floor_layouts: list[FloorLayout] = []
        for idx, floor in enumerate(program.floors):
            floor_rooms = program.rooms_on_floor(floor.id)
            layout = self._layout_floor_with_zones(
                floor=floor,
                floor_rooms=floor_rooms,
                zone_plan=building_zones.floors[floor.id],
                core=core,
                floor_index=idx,
                module=module,
                rng=rng,
            )
            floor_layouts.append(_mirror_wet_stack_onto_floor(layout, primary_stack))

        return LayoutCandidate(
            id=f"candidate-{seed}",
            seed=seed,
            floors=floor_layouts,
            wet_stacks=list(building_zones.wet_stacks),
        )

    def _layout_floor_with_zones(
        self,
        *,
        floor,
        floor_rooms: list[RoomSpec],
        zone_plan: FloorZonePlan,
        core: CorePlacementResult,
        floor_index: int,
        module: float,
        rng: random.Random,
    ) -> FloorLayout:
        layout_rooms: dict[str, _LayoutRoom] = {
            r.id: _LayoutRoom(spec=r, weight=r.target_area) for r in floor_rooms
        }

        # 按 zone 聚合几何（同 zone 多块 rect）
        zone_rects: dict[ArchitecturalZone, list[Rect]] = {}
        zone_room_ids: dict[ArchitecturalZone, list[str]] = {}
        for zg in zone_plan.zones:
            zone_rects.setdefault(zg.zone, []).append(
                Rect(x=zg.rect.x, y=zg.rect.y, width=zg.rect.width, depth=zg.rect.depth)
            )
            if zg.room_ids:
                zone_room_ids[zg.zone] = list(zg.room_ids)

        # WetStack 锚由 candidate.wet_stacks 承载；本层仅做功能区打包
        for zone, room_ids in zone_room_ids.items():
            rects = zone_rects.get(zone, [])
            if not rects or not room_ids:
                continue
            rooms = [
                layout_rooms[rid] for rid in room_ids if rid in layout_rooms
            ]
            rng.shuffle(rooms)
            self._pack_into_rects(rooms, rects, module, rng)

        stair_name = "楼梯" if floor_index > 0 else "楼梯 · 入口"
        stair_placement = RoomPlacement(
            room_id=f"stair-{floor.id}",
            floor_id=floor.id,
            rect=core.rect.model_copy(),
            source=PlacementSource.GENERATED,
            name=stair_name,
            category="circulation",
        )

        placements: list[RoomPlacement] = [stair_placement]
        for lr in layout_rooms.values():
            if lr.rect is None:
                continue
            placements.append(
                RoomPlacement(
                    room_id=lr.spec.id,
                    floor_id=floor.id,
                    rect=lr.rect,
                    source=PlacementSource.PROGRAM,
                    name=lr.spec.name,
                    category=lr.spec.category.value,
                )
            )

        return FloorLayout(
            floor_id=floor.id,
            placements=placements,
            stair_x0=core.rect.x,
            stair_y0=core.rect.y,
            stair_x1=core.rect.right,
            stair_y1=core.rect.bottom,
            core_placement=core.placement.value,
        )

    def _pack_into_rects(
        self,
        rooms: list[_LayoutRoom],
        rects: list[Rect],
        module: float,
        rng: random.Random,
    ) -> None:
        if not rooms or not rects:
            return
        if len(rects) == 1:
            r = rects[0]
            self._layout_rooms(rooms, r.x, r.y, r.right, r.bottom, module, rng)
            return

        total_area = sum(r.area for r in rects) or 1.0
        total_weight = sum(r.weight for r in rooms) or 1.0
        remaining = list(rooms)
        for i, rect in enumerate(rects):
            if not remaining:
                break
            if i == len(rects) - 1:
                share = remaining
                remaining = []
            else:
                target_w = total_weight * (rect.area / total_area)
                cum = 0.0
                split = max(1, len(remaining) - (len(rects) - i - 1))
                for j, lr in enumerate(remaining):
                    cum += lr.weight
                    if cum >= target_w and j + 1 < len(remaining):
                        split = j + 1
                        break
                share = remaining[:split]
                remaining = remaining[split:]
            self._layout_rooms(share, rect.x, rect.y, rect.right, rect.bottom, module, rng)

    def _layout_rooms(
        self,
        rooms: list[_LayoutRoom],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        module: float,
        rng: random.Random,
    ) -> None:
        if not rooms:
            return
        if len(rooms) == 1:
            rooms[0].rect = PlacementRect(
                x=x0, y=y0, width=max(module, x1 - x0), depth=max(module, y1 - y0)
            )
            return

        total = sum(r.weight for r in rooms) or 1.0
        half = total / 2
        cum = 0.0
        split_idx = 1
        for i, r in enumerate(rooms[:-1]):
            cum += r.weight
            if cum >= half:
                split_idx = i + 1
                break

        group1 = rooms[:split_idx]
        group2 = rooms[split_idx:]
        area1 = sum(r.weight for r in group1) or 1.0
        area2 = sum(r.weight for r in group2) or 1.0
        width = x1 - x0
        height = y1 - y0
        frac = area1 / (area1 + area2)

        if abs(width - height) < 1e-6:
            split_horizontal = rng.random() < 0.5
        else:
            split_horizontal = width >= height

        min_span = module * 2
        if split_horizontal:
            cut_x = snap_value(x0 + width * frac, module)
            cut_x = max(x0 + min_span, min(x1 - min_span, cut_x))
            self._layout_rooms(group1, x0, y0, cut_x, y1, module, rng)
            self._layout_rooms(group2, cut_x, y0, x1, y1, module, rng)
        else:
            cut_y = snap_value(y0 + height * frac, module)
            cut_y = max(y0 + min_span, min(y1 - min_span, cut_y))
            self._layout_rooms(group1, x0, y0, x1, cut_y, module, rng)
            self._layout_rooms(group2, x0, cut_y, x1, y1, module, rng)

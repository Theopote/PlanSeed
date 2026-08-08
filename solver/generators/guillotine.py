"""Guillotine 递归切分候选生成器 — 迁移自 reference/floorplan-generator.html。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory, RoomSpec
from solver.geometry.snap import snap_value
from solver.program.floor_assign import assert_all_rooms_placed


@dataclass
class _LayoutRoom:
    spec: RoomSpec
    weight: float
    rect: PlacementRect | None = None


@dataclass
class _FloorState:
    wet_rect: PlacementRect | None = None
    stair_rect: PlacementRect | None = None
    rooms: list[_LayoutRoom] = field(default_factory=list)


class GuillotineGenerator:
    """递归面积切分 + 楼梯/湿区条带对齐。"""

    def generate(self, program: DesignProgram, seed: int) -> LayoutCandidate:
        assert_all_rooms_placed(program.rooms, program.floors)
        rng = random.Random(seed)
        module = program.solver_config.snap_module
        buildable = program.buildable
        w = buildable.width
        d = buildable.depth
        stair_w = program.site.stair_width

        wet_ratio = self._compute_wet_ratio(program)
        floor_layouts: list[FloorLayout] = []

        for idx, floor in enumerate(program.floors):
            floor_rooms = program.rooms_on_floor(floor.id)
            wet = [r for r in floor_rooms if r.category == RoomCategory.WET]
            other = [r for r in floor_rooms if r.category != RoomCategory.WET]

            wet_copy = [_LayoutRoom(spec=r, weight=r.target_area) for r in wet]
            other_copy = [_LayoutRoom(spec=r, weight=r.target_area) for r in other]
            rng.shuffle(wet_copy)
            rng.shuffle(other_copy)

            layout = self._layout_floor(
                floor,
                wet_copy,
                other_copy,
                w,
                d,
                stair_w,
                wet_ratio,
                idx,
                module,
                rng,
            )
            floor_layouts.append(
                FloorLayout(
                    floor_id=floor.id,
                    placements=layout["placements"],
                    wet_zone_x0=layout["wet_x0"],
                    wet_zone_x1=layout["wet_x1"],
                    stair_x0=0.0,
                    stair_x1=stair_w,
                )
            )

        return LayoutCandidate(id=f"candidate-{seed}", seed=seed, floors=floor_layouts)

    def _compute_wet_ratio(self, program: DesignProgram) -> float:
        f0 = program.floors[0]
        rooms = program.rooms_on_floor(f0.id)
        wet_area = sum(r.target_area for r in rooms if r.category == RoomCategory.WET)
        other_area = sum(r.target_area for r in rooms if r.category != RoomCategory.WET)
        total = wet_area + other_area
        return wet_area / total if total > 0 else 0.3

    def _layout_floor(
        self,
        floor,
        wet_rooms: list[_LayoutRoom],
        other_rooms: list[_LayoutRoom],
        w: float,
        d: float,
        stair_w: float,
        wet_ratio: float,
        floor_index: int,
        module: float,
        rng: random.Random,
    ) -> dict:
        remain_x0 = stair_w
        remain_width = w - stair_w
        wet_width = remain_width * wet_ratio

        wet_rect = PlacementRect(x=remain_x0, y=0, width=wet_width, depth=d)
        other_rect = PlacementRect(x=remain_x0 + wet_width, y=0, width=remain_width - wet_width, depth=d)

        if wet_rooms:
            self._layout_rooms(
                wet_rooms,
                wet_rect.x,
                wet_rect.y,
                wet_rect.right,
                wet_rect.bottom,
                module,
                rng,
            )
        if other_rooms:
            self._layout_rooms(
                other_rooms,
                other_rect.x,
                other_rect.y,
                other_rect.right,
                other_rect.bottom,
                module,
                rng,
            )

        stair_name = "玄关 · 楼梯" if floor_index == 0 else "楼梯厅 · 走廊"
        stair_placement = RoomPlacement(
            room_id=f"stair-{floor.id}",
            floor_id=floor.id,
            rect=PlacementRect(x=0, y=0, width=stair_w, depth=d),
            source=PlacementSource.GENERATED,
            name=stair_name,
            category="circulation",
        )

        placements: list[RoomPlacement] = [stair_placement]
        for group in (wet_rooms, other_rooms):
            for lr in group:
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

        return {
            "placements": placements,
            "wet_x0": wet_rect.x,
            "wet_x1": wet_rect.right,
        }

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
            rooms[0].rect = PlacementRect(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)
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

        split_horizontal: bool
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


# Protocol 兼容
assert issubclass(GuillotineGenerator, object)

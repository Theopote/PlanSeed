"""
ZonePlanner — envelope/core 之后、房间切分之前的分区层。

Functional Zone（DAY/NIGHT/SERVICE）决定平面打包；
WetStackGroup（WS1…）决定跨层技术叠置条带，二者分离。
"""

from __future__ import annotations

import random

from packages.schema.layout import PlacementRect, WetStack
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.zoning import (
    ArchitecturalZone,
    BuildingZonePlan,
    FloorZonePlan,
    RoomZoning,
    WetStackGroup,
    ZoneGeometry,
    ZoneRoomGroup,
)
from solver.geometry.rect import Rect
from solver.geometry.snap import snap_value
from solver.semantics.roles import (
    is_garage,
    is_guest_bath,
    is_kitchen,
    is_laundry,
    is_master_bath,
    is_storage,
    is_study,
)


def classify_room(room: RoomSpec) -> RoomZoning:
    """
    房间 → 功能分区 + 可选湿区技术叠组。

    判定依据：category + semantic tags（见 solver.semantics.roles）；
    name 仅作 MVP 冻结回退，不在此扩展中文子串。
    """
    if room.category == RoomCategory.CIRCULATION:
        return RoomZoning(functional_zone=ArchitecturalZone.CIRCULATION)

    if is_kitchen(room):
        return RoomZoning(
            functional_zone=ArchitecturalZone.DAY,
            wet_stack_group=WetStackGroup.WS1,
        )
    if is_master_bath(room):
        return RoomZoning(
            functional_zone=ArchitecturalZone.NIGHT,
            wet_stack_group=WetStackGroup.WS1,
        )
    if is_laundry(room):
        return RoomZoning(
            functional_zone=ArchitecturalZone.SERVICE,
            wet_stack_group=WetStackGroup.WS1,
        )
    if is_guest_bath(room) or (
        room.category == RoomCategory.WET
        and not is_kitchen(room)
        and not is_master_bath(room)
        and not is_laundry(room)
    ):
        return RoomZoning(
            functional_zone=ArchitecturalZone.SERVICE,
            wet_stack_group=WetStackGroup.WS1,
        )

    if room.category == RoomCategory.PUBLIC:
        return RoomZoning(functional_zone=ArchitecturalZone.DAY)
    if room.category == RoomCategory.PRIVATE:
        return RoomZoning(functional_zone=ArchitecturalZone.NIGHT)
    if room.category == RoomCategory.SERVICE:
        return RoomZoning(functional_zone=ArchitecturalZone.SERVICE)
    if is_garage(room) or is_storage(room):
        return RoomZoning(functional_zone=ArchitecturalZone.SERVICE)
    if is_study(room):
        return RoomZoning(functional_zone=ArchitecturalZone.NIGHT)
    if room.category == RoomCategory.OTHER:
        return RoomZoning(functional_zone=ArchitecturalZone.DAY)
    return RoomZoning(functional_zone=ArchitecturalZone.DAY)


def zone_for_room(room: RoomSpec) -> ArchitecturalZone:
    """兼容入口：仅返回功能分区。"""
    return classify_room(room).functional_zone


def wet_stack_group_for_room(room: RoomSpec) -> WetStackGroup | None:
    return classify_room(room).wet_stack_group


class ZonePlanner:
    """
    分区策略：
    - 功能区 DAY/NIGHT/SERVICE：按层在 free_rects 内切分（空区回收）
    - WetStack：整栋共享 anchor_rect（技术对齐参考，不对功能打包抢空间）
    """

    def group_rooms(self, rooms: list[RoomSpec]) -> list[ZoneRoomGroup]:
        buckets: dict[ArchitecturalZone, list[RoomSpec]] = {}
        for room in rooms:
            z = zone_for_room(room)
            if z == ArchitecturalZone.CIRCULATION:
                continue
            buckets.setdefault(z, []).append(room)

        groups: list[ZoneRoomGroup] = []
        for zone, rs in buckets.items():
            groups.append(
                ZoneRoomGroup(
                    zone=zone,
                    room_ids=[r.id for r in rs],
                    target_area=sum(r.target_area for r in rs),
                )
            )
        groups.sort(key=lambda g: g.target_area, reverse=True)
        return groups

    def plan_geometry(
        self,
        *,
        rooms: list[RoomSpec],
        free_rects: list[Rect],
        snap_module: float = 0.3,
        rng: random.Random | None = None,
        floor_id: str = "_shared",
    ) -> list[ZoneGeometry]:
        rng = rng or random.Random(0)
        groups = [g for g in self.group_rooms(rooms) if g.room_ids]
        if not groups or not free_rects:
            return []

        free_rects = sorted(free_rects, key=lambda r: r.area, reverse=True)

        if len(free_rects) == 1 and len(groups) > 1:
            return self._split_rect_into_zones(
                floor_id, free_rects[0], groups, snap_module, rng
            )
        return self._assign_rects_to_zones(floor_id, free_rects, groups)

    def plan_floor(
        self,
        *,
        floor_id: str,
        rooms: list[RoomSpec],
        free_rects: list[Rect],
        snap_module: float = 0.3,
        rng: random.Random | None = None,
    ) -> FloorZonePlan:
        """单层分区（测试 / 单层建筑）。多层请用 plan_building。"""
        zones = self.plan_geometry(
            rooms=rooms,
            free_rects=free_rects,
            snap_module=snap_module,
            rng=rng,
            floor_id=floor_id,
        )
        return FloorZonePlan(floor_id=floor_id, zones=zones)

    def plan_building(
        self,
        *,
        floors: list[tuple[str, list[RoomSpec]]],
        free_rects: list[Rect],
        snap_module: float = 0.3,
        rng: random.Random | None = None,
        max_wet_stacks: int = 1,
        free_rects_by_floor: dict[str, list[Rect]] | None = None,
    ) -> BuildingZonePlan:
        """
        各层按功能区打包（空区回收）；整栋 WetStack 作技术对齐参考。

        MVP：max_wet_stacks=1 → 至多一个 WS1；未来可扩到 WS2。
        厨房进 DAY、主卫进 NIGHT、客卫进 SERVICE — 不再因 WET 挤进同一功能条带。

        free_rects：跨层共享空间（通常只扣 StairCore），供 WetStack 锚点。
        free_rects_by_floor：按层 free space（扣本层 room/zone lock）；缺省回退到 free_rects。
        """
        rng = rng or random.Random(0)
        all_rooms = [r for _, rooms in floors for r in rooms]
        floor_ids = [fid for fid, _ in floors]

        wet_stacks = self._build_wet_stacks(
            free_rects,
            all_rooms=all_rooms,
            floor_ids=floor_ids,
            snap_module=snap_module,
            rng=rng,
            max_wet_stacks=max_wet_stacks,
        )

        floor_plans: dict[str, FloorZonePlan] = {}
        for floor_id, rooms in floors:
            floor_free = (
                free_rects_by_floor.get(floor_id, free_rects)
                if free_rects_by_floor is not None
                else free_rects
            )
            zones = self.plan_geometry(
                rooms=rooms,
                free_rects=floor_free,
                snap_module=snap_module,
                rng=rng,
                floor_id=floor_id,
            )
            floor_plans[floor_id] = FloorZonePlan(floor_id=floor_id, zones=zones)
        return BuildingZonePlan(floors=floor_plans, wet_stacks=wet_stacks)

    def _build_wet_stacks(
        self,
        free_rects: list[Rect],
        *,
        all_rooms: list[RoomSpec],
        floor_ids: list[str],
        snap_module: float,
        rng: random.Random,
        max_wet_stacks: int,
    ) -> list[WetStack]:
        """
        按 WS 成员面积占比切出共享 anchor_rect。

        不从功能打包空间扣除 — 叠置语义与功能邻接解耦（Phase 2 再做 shaft 路由）。
        MVP 仅产出至多 1 个 WS1；max_wet_stacks≥2 时预留扩展点。
        """
        n = max(1, min(2, max_wet_stacks))
        members = [r for r in all_rooms if wet_stack_group_for_room(r) is not None]
        if not members or not free_rects:
            return []

        # MVP：全部湿区成员归入 WS1；未来按组拆分 WS1/WS2
        stacks: list[WetStack] = []
        for i, group in enumerate((WetStackGroup.WS1, WetStackGroup.WS2)[:n]):
            if i > 0:
                break  # Phase 1.6：尚未实现第二叠组分配
            group_rooms = members if i == 0 else []
            if not group_rooms:
                continue
            ws_weight = sum(r.target_area for r in group_rooms)
            other_weight = sum(r.target_area for r in all_rooms) - ws_weight
            bands, _ = self._carve_band(
                free_rects,
                band_weight=ws_weight,
                other_weight=max(0.0, other_weight),
                snap_module=snap_module,
                rng=rng,
                min_frac=0.10,
                max_frac=0.35,
            )
            if not bands:
                continue
            stacks.append(
                WetStack(
                    id=group.value,
                    anchor_rect=bands[0],
                    floor_ids=list(floor_ids),
                    member_room_ids=[r.id for r in group_rooms],
                )
            )
        return stacks

    def _carve_band(
        self,
        free_rects: list[Rect],
        *,
        band_weight: float,
        other_weight: float,
        snap_module: float,
        rng: random.Random,
        min_frac: float = 0.12,
        max_frac: float = 0.45,
    ) -> tuple[list[PlacementRect], list[Rect]]:
        """从最大剩余矩形切出一条带；返回 (band_rects, residual)。"""
        if not free_rects:
            return [], []

        free_rects = sorted(free_rects, key=lambda r: r.area, reverse=True)
        if band_weight <= 1e-9:
            return [], list(free_rects)

        total_w = band_weight + other_weight
        frac = band_weight / total_w if total_w > 1e-9 else 0.25
        frac = max(min_frac, min(max_frac, frac))

        primary = free_rects[0]
        others = free_rects[1:]
        total_free = sum(r.area for r in free_rects)
        target_area = frac * total_free

        vertical_band = primary.width >= primary.depth
        if abs(primary.width - primary.depth) < 1e-6:
            vertical_band = rng.random() < 0.5

        min_span = snap_module * 2
        if vertical_band:
            raw_w = target_area / max(primary.depth, 1e-9)
            band = snap_value(raw_w, snap_module)
            band = max(min_span, min(primary.width - min_span, band))
            service = PlacementRect(
                x=primary.right - band,
                y=primary.y,
                width=band,
                depth=primary.depth,
            )
            rem = Rect(
                x=primary.x,
                y=primary.y,
                width=max(snap_module, primary.width - band),
                depth=primary.depth,
            )
        else:
            raw_d = target_area / max(primary.width, 1e-9)
            band = snap_value(raw_d, snap_module)
            band = max(min_span, min(primary.depth - min_span, band))
            service = PlacementRect(
                x=primary.x,
                y=primary.bottom - band,
                width=primary.width,
                depth=band,
            )
            rem = Rect(
                x=primary.x,
                y=primary.y,
                width=primary.width,
                depth=max(snap_module, primary.depth - band),
            )

        residual = [rem] + list(others)
        residual = [r for r in residual if r.width > 1e-9 and r.depth > 1e-9]
        return [service], residual

    def _split_rect_into_zones(
        self,
        floor_id: str,
        rect: Rect,
        groups: list[ZoneRoomGroup],
        module: float,
        rng: random.Random,
    ) -> list[ZoneGeometry]:
        total = sum(g.target_area for g in groups) or 1.0
        horizontal = rect.width >= rect.depth
        if abs(rect.width - rect.depth) < 1e-6:
            horizontal = rng.random() < 0.5

        cursor = rect.x if horizontal else rect.y
        end = rect.right if horizontal else rect.bottom
        span = end - cursor
        geometries: list[ZoneGeometry] = []

        for i, group in enumerate(groups):
            if i == len(groups) - 1:
                cut = end
            else:
                frac = group.target_area / total
                raw = cursor + span * frac
                cut = snap_value(raw, module)
                min_span = module * 2
                cut = max(cursor + min_span, min(end - min_span * (len(groups) - i - 1), cut))

            if horizontal:
                zr = PlacementRect(
                    x=cursor, y=rect.y, width=max(module, cut - cursor), depth=rect.depth
                )
            else:
                zr = PlacementRect(
                    x=rect.x, y=cursor, width=rect.width, depth=max(module, cut - cursor)
                )
            geometries.append(
                ZoneGeometry(
                    zone=group.zone,
                    floor_id=floor_id,
                    rect=zr,
                    room_ids=list(group.room_ids),
                )
            )
            cursor = cut

        return geometries

    def _assign_rects_to_zones(
        self,
        floor_id: str,
        free_rects: list[Rect],
        groups: list[ZoneRoomGroup],
    ) -> list[ZoneGeometry]:
        """把 stair 切分后的多块 free rect 按目标面积缺口分给各功能区。"""
        geometries: list[ZoneGeometry] = []
        if not groups or not free_rects:
            return geometries

        rects = sorted(free_rects, key=lambda r: r.area, reverse=True)
        remaining_need = {g.zone: g.target_area for g in groups}
        buckets: dict[ArchitecturalZone, list[Rect]] = {g.zone: [] for g in groups}

        for rect in rects:
            best = max(groups, key=lambda g: remaining_need.get(g.zone, 0.0))
            buckets[best.zone].append(rect)
            remaining_need[best.zone] = max(
                0.0, remaining_need[best.zone] - rect.area
            )

        for group in groups:
            for rect in buckets[group.zone]:
                geometries.append(
                    ZoneGeometry(
                        zone=group.zone,
                        floor_id=floor_id,
                        rect=PlacementRect(
                            x=rect.x, y=rect.y, width=rect.width, depth=rect.depth
                        ),
                        room_ids=list(group.room_ids),
                    )
                )
        return geometries


def rooms_for_zone(
    rooms: list[RoomSpec], zone_geom: ZoneGeometry
) -> list[RoomSpec]:
    id_set = set(zone_geom.room_ids)
    return [r for r in rooms if r.id in id_set]

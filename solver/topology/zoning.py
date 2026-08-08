"""
ZonePlanner — envelope/core 之后、房间切分之前的分区层。

DesignProgram rooms
      ↓
zone assignment (day/night/service)
      ↓
zone geometry in free rects
      ↓
RoomLayout (Guillotine) within each zone
"""

from __future__ import annotations

import random

from packages.schema.layout import PlacementRect
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.zoning import (
    ArchitecturalZone,
    FloorZonePlan,
    ZoneGeometry,
    ZoneRoomGroup,
)
from solver.geometry.rect import Rect
from solver.geometry.snap import snap_value


def zone_for_room(room: RoomSpec) -> ArchitecturalZone:
    """房间 → 建筑分区（可解释默认映射）。"""
    tags = {t.lower() for t in room.tags}
    name = room.name

    if room.category == RoomCategory.CIRCULATION:
        return ArchitecturalZone.CIRCULATION
    if room.category == RoomCategory.PUBLIC:
        return ArchitecturalZone.DAY
    if room.category == RoomCategory.PRIVATE:
        return ArchitecturalZone.NIGHT
    if room.category == RoomCategory.SERVICE:
        return ArchitecturalZone.SERVICE
    if room.category == RoomCategory.WET:
        return ArchitecturalZone.SERVICE
    if "garage" in tags or "车库" in name or "储藏" in name:
        return ArchitecturalZone.SERVICE
    if "书房" in name or "study" in tags:
        return ArchitecturalZone.NIGHT
    if room.category == RoomCategory.OTHER:
        return ArchitecturalZone.DAY
    return ArchitecturalZone.DAY


class ZonePlanner:
    """
    第一版：按面积权重把剩余矩形分配给 day/night/service。

    circulation 通常已由 StairCore 占据，不参与房间分区切分。
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
        """
        将 free_rects 切成各 zone 的几何容器（不含楼层绑定）。

        策略：
        1. 按 zone 面积权重排序
        2. 若仅一块剩余矩形且多 zone → 按权重切分成条带
        3. 若多块剩余矩形 → 贪心把矩形分给 zone
        """
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
    ) -> dict[str, FloorZonePlan]:
        """
        整栋共享分区几何，再按层绑定房间。

        跨层湿区/服务区对齐依赖同一套 SERVICE 矩形；
        面积权重取各层房间合计，使 day（多为 F1）与 night（多为 F2）
        同时进入切分，避免每层各自切出不同 service 带。
        """
        all_rooms = [r for _, rooms in floors for r in rooms]
        shared = self.plan_geometry(
            rooms=all_rooms,
            free_rects=free_rects,
            snap_module=snap_module,
            rng=rng,
            floor_id="_shared",
        )
        plans: dict[str, FloorZonePlan] = {}
        for floor_id, rooms in floors:
            room_ids = {r.id for r in rooms}
            zones = [
                ZoneGeometry(
                    zone=zg.zone,
                    floor_id=floor_id,
                    rect=zg.rect.model_copy(),
                    room_ids=[rid for rid in zg.room_ids if rid in room_ids],
                )
                for zg in shared
            ]
            plans[floor_id] = FloorZonePlan(floor_id=floor_id, zones=zones)
        return plans

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
        geometries: list[ZoneGeometry] = []
        rects = list(free_rects)
        for i, group in enumerate(groups):
            if not rects:
                break
            if i == len(groups) - 1:
                # 剩余矩形全部给最后一个 zone（合并为多条 ZoneGeometry 或取最大）
                for r in rects:
                    geometries.append(
                        ZoneGeometry(
                            zone=group.zone,
                            floor_id=floor_id,
                            rect=PlacementRect(x=r.x, y=r.y, width=r.width, depth=r.depth),
                            room_ids=list(group.room_ids) if r is rects[0] else [],
                        )
                    )
                # 房间只挂在第一块上，其余块仍属同 zone 供布局合并
                if len(rects) > 1:
                    geometries[-len(rects)].room_ids = list(group.room_ids)
                    for g in geometries[-len(rects) + 1 :]:
                        g.room_ids = []
                break
            r = rects.pop(0)
            geometries.append(
                ZoneGeometry(
                    zone=group.zone,
                    floor_id=floor_id,
                    rect=PlacementRect(x=r.x, y=r.y, width=r.width, depth=r.depth),
                    room_ids=list(group.room_ids),
                )
            )
        return geometries


def rooms_for_zone(
    rooms: list[RoomSpec], zone_geom: ZoneGeometry
) -> list[RoomSpec]:
    id_set = set(zone_geom.room_ids)
    return [r for r in rooms if r.id in id_set]

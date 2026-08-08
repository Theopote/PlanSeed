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
    分区策略：
    - SERVICE：整栋共享一条带（湿区跨层对齐）
    - DAY / NIGHT：按层在剩余空间内切分；本层无房间的 zone 不占位（空区回收）
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
        整栋共享 SERVICE 带；各层在剩余区内只切本层有房间的 day/night。

        空区回收：F1 无 night 房间时，night 不占 residual；空间归 day（反之亦然）。
        """
        rng = rng or random.Random(0)
        all_rooms = [r for _, rooms in floors for r in rooms]
        service_weight = sum(
            r.target_area for r in all_rooms if zone_for_room(r) == ArchitecturalZone.SERVICE
        )
        other_weight = sum(
            r.target_area
            for r in all_rooms
            if zone_for_room(r)
            in (ArchitecturalZone.DAY, ArchitecturalZone.NIGHT)
        )

        service_rects, residual = self._carve_service_band(
            free_rects,
            service_weight=service_weight,
            other_weight=other_weight,
            snap_module=snap_module,
            rng=rng,
        )

        plans: dict[str, FloorZonePlan] = {}
        for floor_id, rooms in floors:
            zones: list[ZoneGeometry] = []
            service_ids = [
                r.id for r in rooms if zone_for_room(r) == ArchitecturalZone.SERVICE
            ]
            for i, pr in enumerate(service_rects):
                zones.append(
                    ZoneGeometry(
                        zone=ArchitecturalZone.SERVICE,
                        floor_id=floor_id,
                        rect=pr.model_copy(),
                        room_ids=list(service_ids) if i == 0 else [],
                    )
                )

            local_rooms = [
                r
                for r in rooms
                if zone_for_room(r)
                in (ArchitecturalZone.DAY, ArchitecturalZone.NIGHT)
            ]
            if local_rooms and residual:
                zones.extend(
                    self.plan_geometry(
                        rooms=local_rooms,
                        free_rects=residual,
                        snap_module=snap_module,
                        rng=rng,
                        floor_id=floor_id,
                    )
                )
            elif local_rooms and not residual and service_rects:
                # 极端：无 residual 时把 day/night 并入 service 几何（仍可放置）
                zones[0].room_ids = list(service_ids) + [r.id for r in local_rooms]

            plans[floor_id] = FloorZonePlan(floor_id=floor_id, zones=zones)
        return plans

    def _carve_service_band(
        self,
        free_rects: list[Rect],
        *,
        service_weight: float,
        other_weight: float,
        snap_module: float,
        rng: random.Random,
    ) -> tuple[list[PlacementRect], list[Rect]]:
        """
        从最大剩余矩形切出共享 SERVICE 条带；其余矩形 + 切余 → residual。

        无 service 权重时：不切带，全部 residual。
        """
        if not free_rects:
            return [], []

        free_rects = sorted(free_rects, key=lambda r: r.area, reverse=True)
        if service_weight <= 1e-9:
            return [], list(free_rects)

        total_w = service_weight + other_weight
        frac = service_weight / total_w if total_w > 1e-9 else 0.25
        # 夹紧：service 至少约占 12%，至多 45%，避免挤死或吃光
        frac = max(0.12, min(0.45, frac))

        primary = free_rects[0]
        others = free_rects[1:]
        total_free = sum(r.area for r in free_rects)
        target_area = frac * total_free

        # 优先切竖直条带（跨层 x 对齐更稳）；近似方块时由 rng 决定
        vertical_band = primary.width >= primary.depth
        if abs(primary.width - primary.depth) < 1e-6:
            vertical_band = rng.random() < 0.5

        min_span = snap_module * 2
        if vertical_band:
            raw_w = target_area / max(primary.depth, 1e-9)
            band = snap_value(raw_w, snap_module)
            band = max(min_span, min(primary.width - min_span, band))
            # 条带贴右缘（湿区常见靠端）
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
        geometries: list[ZoneGeometry] = []
        rects = list(free_rects)
        for i, group in enumerate(groups):
            if not rects:
                break
            if i == len(groups) - 1:
                for r in rects:
                    geometries.append(
                        ZoneGeometry(
                            zone=group.zone,
                            floor_id=floor_id,
                            rect=PlacementRect(x=r.x, y=r.y, width=r.width, depth=r.depth),
                            room_ids=list(group.room_ids) if r is rects[0] else [],
                        )
                    )
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

"""
ZonePlanner — envelope/core 之后、房间切分之前的分区层。

Functional Zone（DAY/NIGHT/SERVICE）决定平面打包；
WetStackGroup（WS1…）决定跨层技术叠置条带，二者分离。
"""

from __future__ import annotations

import random

from packages.schema.layout import PlacementRect, WetStack
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge
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
    is_foyer,
    is_garage,
    is_guest_bath,
    is_kitchen,
    is_laundry,
    is_living,
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
        entry_model_edge: CardinalEdge | None = None,
        wet_exterior_ends: bool = False,
    ) -> list[ZoneGeometry]:
        rng = rng or random.Random(0)
        groups = [g for g in self.group_rooms(rooms) if g.room_ids]
        if not groups or not free_rects:
            return []

        free_rects = sorted(free_rects, key=lambda r: r.area, reverse=True)
        # 仅一层：卫浴区贴切分两端，避免 SERVICE 夹心导致黑卫
        if wet_exterior_ends:
            groups = _order_groups_for_wet_exterior(groups, rooms)

        if len(free_rects) == 1 and len(groups) > 1:
            return self._split_rect_into_zones(
                floor_id,
                free_rects[0],
                groups,
                snap_module,
                rng,
                rooms=rooms,
                entry_model_edge=entry_model_edge,
                wet_exterior_ends=wet_exterior_ends,
            )
        # 多块 free：先按面积排序，再把贴入口边的碎块优先给 DAY
        groups = _order_groups_for_entry(
            groups, rooms, entry_model_edge=entry_model_edge
        )
        return self._assign_rects_to_zones(
            floor_id,
            free_rects,
            groups,
            rooms=rooms,
            entry_model_edge=entry_model_edge,
            wet_exterior_ends=wet_exterior_ends,
            snap_module=snap_module,
            rng=rng,
        )

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
            wet_exterior_ends=True,
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
        entry_model_edge: CardinalEdge | None = None,
        ground_floor_id: str | None = None,
    ) -> BuildingZonePlan:
        """
        各层按功能区打包（空区回收）；整栋 WetStack 作技术对齐参考。

        MVP：max_wet_stacks=1 → 至多一个 WS1；未来可扩到 WS2。
        厨房进 DAY、主卫进 NIGHT、客卫进 SERVICE — 不再因 WET 挤进同一功能条带。

        free_rects：跨层共享空间（通常只扣 StairCore），供 WetStack 锚点。
        free_rects_by_floor：按层 free space（扣本层 room/zone lock）；缺省回退到 free_rects。
        entry_model_edge：仅对 ground_floor 生效，把 DAY/门厅区贴到入口边。
        """
        rng = rng or random.Random(0)
        all_rooms = [r for _, rooms in floors for r in rooms]
        floor_ids = [fid for fid, _ in floors]
        ground = ground_floor_id or (floor_ids[0] if floor_ids else None)

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
            edge = entry_model_edge if floor_id == ground else None
            # 不在 plan_building 开 wet_exterior_ends：一层 B06 valid 0.50→0.375
            # 且 draft AB 不升；卫浴外墙改由区内打包 exterior_bonus 承担。
            zones = self.plan_geometry(
                rooms=rooms,
                free_rects=floor_free,
                snap_module=snap_module,
                rng=rng,
                floor_id=floor_id,
                entry_model_edge=edge,
                wet_exterior_ends=False,
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
        *,
        rooms: list[RoomSpec] | None = None,
        entry_model_edge: CardinalEdge | None = None,
        wet_exterior_ends: bool = False,
    ) -> list[ZoneGeometry]:
        total = sum(g.target_area for g in groups) or 1.0
        by_id = {r.id: r for r in (rooms or [])}
        has_entry_public = any(
            _group_has_foyer(g, by_id) or _group_has_living(g, by_id) for g in groups
        )

        # 有门厅/客厅时优先沿入口法向切开，使公区能贴入口边
        horizontal = rect.width >= rect.depth
        if abs(rect.width - rect.depth) < 1e-6:
            horizontal = rng.random() < 0.5
        if has_entry_public and entry_model_edge is not None:
            min_span = module * 4
            if (
                entry_model_edge in (CardinalEdge.WEST, CardinalEdge.EAST)
                and rect.width >= min_span
            ):
                horizontal = True
            elif (
                entry_model_edge in (CardinalEdge.NORTH, CardinalEdge.SOUTH)
                and rect.depth >= min_span
            ):
                horizontal = False

        axis_aligned = (
            (horizontal and entry_model_edge in (CardinalEdge.WEST, CardinalEdge.EAST))
            or (
                (not horizontal)
                and entry_model_edge in (CardinalEdge.NORTH, CardinalEdge.SOUTH)
            )
        )
        # 门厅/客厅贴入口边；一层时再把卫浴区固定在切分两端
        ordered = (
            _order_groups_for_entry(
                groups, rooms or [], entry_model_edge=entry_model_edge
            )
            if axis_aligned
            else list(groups)
        )
        if wet_exterior_ends:
            ordered = _pin_wet_groups_to_ends(ordered, rooms or [])

        cursor = rect.x if horizontal else rect.y
        end = rect.right if horizontal else rect.bottom
        span = end - cursor
        geometries: list[ZoneGeometry] = []

        for i, group in enumerate(ordered):
            if i == len(ordered) - 1:
                cut = end
            else:
                frac = group.target_area / total
                raw = cursor + span * frac
                cut = snap_value(raw, module)
                min_span = module * 2
                cut = max(
                    cursor + min_span,
                    min(end - min_span * (len(ordered) - i - 1), cut),
                )

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
        *,
        rooms: list[RoomSpec] | None = None,
        entry_model_edge: CardinalEdge | None = None,
        wet_exterior_ends: bool = False,
        snap_module: float = 0.3,
        rng: random.Random | None = None,
    ) -> list[ZoneGeometry]:
        """把 stair 切分后的多块 free rect 按目标面积缺口分给各功能区。"""
        geometries: list[ZoneGeometry] = []
        if not groups or not free_rects:
            return geometries

        rng = rng or random.Random(0)
        rects = sorted(free_rects, key=lambda r: r.area, reverse=True)
        remaining_need = {g.zone: g.target_area for g in groups}
        buckets: dict[ArchitecturalZone, list[Rect]] = {g.zone: [] for g in groups}
        by_id = {r.id: r for r in (rooms or [])}
        foyer_zone = next(
            (g.zone for g in groups if _group_has_foyer(g, by_id)),
            None,
        )
        wet_zone = next(
            (g.zone for g in groups if _group_needs_exterior_wet(g, by_id)),
            None,
        )
        total_free = sum(r.area for r in free_rects) or 1.0

        def _bucket_rect(zone: ArchitecturalZone, rect: Rect) -> None:
            buckets[zone].append(rect)
            remaining_need[zone] = max(0.0, remaining_need[zone] - rect.area)

        for rect in rects:
            hungry = [g for g in groups if remaining_need.get(g.zone, 0.0) > 1e-9]
            # 仅「一大两小」主导块（>55% 总 free）：整给 DAY 会饿死 SERVICE/NIGHT
            # 过宽的 1.5×need 会在多层车库案打崩 valid
            dominant = rect.area > total_free * 0.55
            if len(hungry) >= 2 and dominant:
                split_groups = [
                    ZoneRoomGroup(
                        zone=g.zone,
                        room_ids=list(g.room_ids),
                        target_area=max(remaining_need[g.zone], 1e-6),
                    )
                    for g in hungry
                ]
                parts = self._split_rect_into_zones(
                    floor_id,
                    rect,
                    split_groups,
                    snap_module,
                    rng,
                    rooms=rooms,
                    entry_model_edge=entry_model_edge,
                    wet_exterior_ends=wet_exterior_ends,
                )
                for zg in parts:
                    _bucket_rect(
                        zg.zone,
                        Rect(
                            x=zg.rect.x,
                            y=zg.rect.y,
                            width=zg.rect.width,
                            depth=zg.rect.depth,
                        ),
                    )
                continue

            foyer_need = remaining_need.get(foyer_zone, 0.0) if foyer_zone else 0.0
            wet_need = remaining_need.get(wet_zone, 0.0) if wet_zone else 0.0
            # 仅把「面积不太离谱」的贴边碎块给门厅组，避免整块大区饿死 SERVICE
            foyer_edge_ok = (
                entry_model_edge is not None
                and foyer_zone is not None
                and foyer_need > 1e-9
                and rect.area <= max(foyer_need * 3.0, 24.0)
                and _rect_touches_edge(rect, entry_model_edge, free_rects)
            )
            wet_edge_ok = (
                wet_exterior_ends
                and wet_zone is not None
                and wet_need > 1e-9
                and rect.area <= max(wet_need * 3.0, 20.0)
                and _rect_touches_any_perimeter(rect, free_rects)
            )
            if foyer_edge_ok:
                best_zone = foyer_zone
            elif wet_edge_ok:
                best_zone = wet_zone
            else:
                # 尚未分到任何块的缺口区优先，避免 SERVICE 空仓
                unserved = [
                    g
                    for g in groups
                    if not buckets[g.zone] and remaining_need.get(g.zone, 0.0) > 1e-9
                ]
                if unserved:
                    best_zone = max(
                        unserved, key=lambda g: remaining_need.get(g.zone, 0.0)
                    ).zone
                elif all(
                    remaining_need.get(g.zone, 0.0) <= 1e-9 for g in groups
                ):
                    # 缺口已满：楼梯旁碎块不再塞进 DAY，否则厨房会被扔进 7㎡ 条带
                    continue
                else:
                    best_zone = max(
                        groups, key=lambda g: remaining_need.get(g.zone, 0.0)
                    ).zone
            _bucket_rect(best_zone, rect)

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


def _group_has_foyer(
    group: ZoneRoomGroup, rooms_by_id: dict[str, RoomSpec]
) -> bool:
    """门厅触发入口区重排。"""
    for rid in group.room_ids:
        room = rooms_by_id.get(rid)
        if room is not None and is_foyer(room):
            return True
    return False


def _group_has_living(
    group: ZoneRoomGroup, rooms_by_id: dict[str, RoomSpec]
) -> bool:
    for rid in group.room_ids:
        room = rooms_by_id.get(rid)
        if room is not None and is_living(room):
            return True
    return False


def _group_needs_exterior_wet(
    group: ZoneRoomGroup, rooms_by_id: dict[str, RoomSpec]
) -> bool:
    for rid in group.room_ids:
        room = rooms_by_id.get(rid)
        if room is not None and (is_guest_bath(room) or is_master_bath(room)):
            return True
    return False


def _order_groups_for_wet_exterior(
    groups: list[ZoneRoomGroup],
    rooms: list[RoomSpec],
) -> list[ZoneRoomGroup]:
    """一层专用（多块 free 预排）：卫浴区贴切分两端。"""
    return _pin_wet_groups_to_ends(groups, rooms)


def _pin_wet_groups_to_ends(
    groups: list[ZoneRoomGroup],
    rooms: list[RoomSpec],
) -> list[ZoneRoomGroup]:
    """
    含卫浴分区贴切分两端，避免夹心黑卫。

    一个卫浴区 → 末端；两个及以上 → 最小/次小分置首尾。
    已在入口侧的门厅组尽量不动：若湿区被赶到入口端且首端已是门厅，改挂到另一端。
    """
    if len(groups) < 2:
        return groups
    by_id = {r.id: r for r in rooms}
    wet_groups = sorted(
        (g for g in groups if _group_needs_exterior_wet(g, by_id)),
        key=lambda g: (g.target_area, g.zone.value),
    )
    if not wet_groups:
        return groups
    rest = [g for g in groups if g not in wet_groups]
    if len(wet_groups) == 1:
        wet = wet_groups[0]
        if rest and _group_has_foyer(rest[0], by_id):
            return [*rest, wet]
        if rest and _group_has_foyer(rest[-1], by_id):
            return [wet, *rest]
        return [*rest, wet]
    return [wet_groups[0], *rest, wet_groups[1]]


def _order_groups_for_entry(
    groups: list[ZoneRoomGroup],
    rooms: list[RoomSpec],
    *,
    entry_model_edge: CardinalEdge | None,
) -> list[ZoneRoomGroup]:
    """
    入口低坐标侧（W/N）把入口公区组放到切分前端；高坐标侧（E/S）放到后端。

    优先门厅；无门厅时退到含客厅的 DAY（一层适老等），避免入口只接到走廊。
    """
    if entry_model_edge is None or len(groups) < 2:
        return groups
    by_id = {r.id: r for r in rooms}
    foyer_groups = [g for g in groups if _group_has_foyer(g, by_id)]
    living_groups = [g for g in groups if _group_has_living(g, by_id)]
    candidates = foyer_groups or living_groups
    if not candidates:
        return groups
    prefer = min(candidates, key=lambda g: (g.target_area, g.zone.value))
    rest = [g for g in groups if g is not prefer]
    if entry_model_edge in (CardinalEdge.WEST, CardinalEdge.NORTH):
        return [prefer, *rest]
    if entry_model_edge in (CardinalEdge.EAST, CardinalEdge.SOUTH):
        return [*rest, prefer]
    return groups


def _rect_touches_edge(
    rect: Rect,
    edge: CardinalEdge,
    all_rects: list[Rect],
) -> bool:
    """相对本层 free 包络判断是否贴入口边。"""
    if not all_rects:
        return False
    min_x = min(r.x for r in all_rects)
    max_x = max(r.right for r in all_rects)
    min_y = min(r.y for r in all_rects)
    max_y = max(r.bottom for r in all_rects)
    eps = 1e-6
    if edge == CardinalEdge.WEST:
        return abs(rect.left - min_x) <= eps
    if edge == CardinalEdge.EAST:
        return abs(rect.right - max_x) <= eps
    if edge == CardinalEdge.NORTH:
        return abs(rect.top - min_y) <= eps
    if edge == CardinalEdge.SOUTH:
        return abs(rect.bottom - max_y) <= eps
    return False


def _rect_touches_any_perimeter(rect: Rect, all_rects: list[Rect]) -> bool:
    """碎块是否贴本层 free 包络任意一边（一层卫浴外墙偏好）。"""
    return any(
        _rect_touches_edge(rect, edge, all_rects)
        for edge in (
            CardinalEdge.WEST,
            CardinalEdge.EAST,
            CardinalEdge.NORTH,
            CardinalEdge.SOUTH,
        )
    )

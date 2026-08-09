"""Guillotine 递归切分 — ZonePlanner 之后的 RoomLayout strategy。"""

from __future__ import annotations

import random
from dataclasses import dataclass

from packages.schema.core import CorePlacementResult
from packages.schema.identity import GENERATOR_VERSION
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
    WetStack,
    ZonePlacement,
)
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.provenance import build_solver_provenance, provenance_to_metrics
from packages.schema.room import RoomSpec
from packages.schema.topology import TopologyPlan
from packages.schema.zoning import ArchitecturalZone, FloorZonePlan, ZoneGeometry

from solver.circulation.stair_core import (
    CorePlacementFailure,
    choose_core_placement,
    core_from_locked_rect,
    place_stair_core_resolving,
    resolve_stair_core_spec,
)
from solver.geometry.free_rects import subtract_rects
from solver.geometry.rect import Rect
from solver.geometry.snap import snap_value
from solver.program.floor_assignment import assert_all_rooms_placed
from solver.topology.derive_access import ensure_access_graph
from solver.topology.plan import (
    TopologyPlanner,
    bipartition_slicing_units,
    group_into_slicing_units,
    order_rooms_for_zone,
    split_avoid_groups,
)
from solver.topology.zoning import ZonePlanner, zone_for_room


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
    Generator #1 — Baseline Guillotine packing strategy（LayoutGenerator）。

    流水线：
      StairCore → free rects → ZonePlanner → TopologyPlan 序/簇 → Guillotine
    """

    strategy_id = "guillotine"
    generator_version = GENERATOR_VERSION


    def __init__(self) -> None:
        self._zone_planner = ZonePlanner()
        self._topology_planner = TopologyPlanner()

    def generate(
        self,
        program: DesignProgram,
        seed: int,
        locks: LayoutLocks | None = None,
        topology: TopologyPlan | None = None,
    ) -> LayoutCandidate:
        assert_all_rooms_placed(program.rooms, program.floors)
        rng = random.Random(seed)
        module = program.solver_config.snap_module
        buildable = program.buildable
        w = buildable.width
        d = buildable.depth
        locks = locks or LayoutLocks()
        locked_ids = locks.locked_room_ids

        ensure_access_graph(program)
        if topology is None:
            topology = self._topology_planner.plan(program)

        if locks.stair is not None:
            core = core_from_locked_rect(
                x=locks.stair.x,
                y=locks.stair.y,
                width=locks.stair.width,
                depth=locks.stair.depth,
                core_placement=locks.stair.core_placement,
            )
        else:
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
                unfit_prov = build_solver_provenance(
                    generator_strategy=self.strategy_id,
                    generator_version=self.generator_version,
                    program=program,
                )
                return LayoutCandidate(
                    id=f"candidate-{seed}",
                    seed=seed,
                    floors=[
                        FloorLayout(floor_id=fl.id, placements=[])
                        for fl in program.floors
                    ],
                    provenance=unfit_prov,
                    metrics={
                        "core_unfit": True,
                        "core_unfit_reason": str(err),
                        **provenance_to_metrics(unfit_prov),
                    },
                )

        floor_rect = Rect(x=0, y=0, width=w, depth=d)
        core_rect = Rect(
            x=core.rect.x, y=core.rect.y, width=core.rect.width, depth=core.rect.depth
        )
        # 跨层共享 free：只扣 StairCore（房间/分区锁不得投影到其它层）
        shared_free = subtract_rects([floor_rect], [core_rect])

        def _holes_on_floor(floor_id: str) -> list[Rect]:
            room_holes = [
                Rect(x=r.x, y=r.y, width=r.width, depth=r.depth)
                for r in locks.rooms_on_floor(floor_id)
            ]
            zone_holes = [
                Rect(x=z.x, y=z.y, width=z.width, depth=z.depth)
                for z in locks.zones_on_floor(floor_id)
            ]
            return [*room_holes, *zone_holes]

        def _free_on_floor(floor_id: str) -> list[Rect]:
            holes = _holes_on_floor(floor_id)
            if not holes:
                return list(shared_free)
            return subtract_rects([floor_rect], [core_rect, *holes])

        def _unlocked_for_planning(
            floor_id: str, rooms: list[RoomSpec]
        ) -> list[RoomSpec]:
            locked_kinds = locks.locked_zone_kinds_on_floor(floor_id)
            out: list[RoomSpec] = []
            for r in rooms:
                if r.id in locked_ids:
                    continue
                if zone_for_room(r).value in locked_kinds:
                    continue
                out.append(r)
            return out

        floor_room_lists = [
            (
                floor.id,
                _unlocked_for_planning(floor.id, program.rooms_on_floor(floor.id)),
            )
            for floor in program.floors
        ]
        free_rects_by_floor = {
            floor.id: _free_on_floor(floor.id) for floor in program.floors
        }
        building_zones = self._zone_planner.plan_building(
            floors=floor_room_lists,
            free_rects=shared_free,
            free_rects_by_floor=free_rects_by_floor,
            snap_module=module,
            rng=rng,
            max_wet_stacks=program.solver_config.max_wet_stacks,
        )
        if locks.zones:
            self._inject_locked_zones(program, locks, building_zones)
        primary_stack = building_zones.wet_stacks[0] if building_zones.wet_stacks else None

        floor_layouts: list[FloorLayout] = []
        zone_placements: list[ZonePlacement] = []
        for idx, floor in enumerate(program.floors):
            floor_rooms = [
                r for r in program.rooms_on_floor(floor.id) if r.id not in locked_ids
            ]
            zone_plan = building_zones.floors.get(
                floor.id, FloorZonePlan(floor_id=floor.id, zones=[])
            )
            layout = self._layout_floor_with_zones(
                floor=floor,
                floor_rooms=floor_rooms,
                zone_plan=zone_plan,
                core=core,
                floor_index=idx,
                module=module,
                rng=rng,
                topology=topology,
                access_graph=program.access_graph,
            )
            # 合并锁定房间放置
            locked_on_floor = locks.rooms_on_floor(floor.id)
            if locked_on_floor:
                extra = [
                    RoomPlacement(
                        room_id=lr.room_id,
                        floor_id=lr.floor_id,
                        rect=PlacementRect(
                            x=lr.x, y=lr.y, width=lr.width, depth=lr.depth
                        ),
                        source=PlacementSource.PROGRAM,
                        name=next(
                            (r.name for r in program.rooms if r.id == lr.room_id),
                            lr.room_id,
                        ),
                        category=next(
                            (
                                r.category.value
                                for r in program.rooms
                                if r.id == lr.room_id
                            ),
                            "other",
                        ),
                    )
                    for lr in locked_on_floor
                ]
                layout = layout.model_copy(
                    update={"placements": list(layout.placements) + extra}
                )
            floor_layouts.append(_mirror_wet_stack_onto_floor(layout, primary_stack))
            kind_counts: dict[str, int] = {}
            for zg in zone_plan.zones:
                kind = (
                    zg.zone.value if hasattr(zg.zone, "value") else str(zg.zone)
                )
                zid = self._stable_zone_id(
                    locks=locks,
                    floor_id=floor.id,
                    kind=kind,
                    rect=zg.rect,
                    kind_counts=kind_counts,
                )
                zone_placements.append(
                    ZonePlacement(
                        id=zid,
                        zone=kind,
                        kind=kind,
                        floor_id=zg.floor_id,
                        rect=zg.rect.model_copy(),
                        room_ids=list(zg.room_ids),
                    )
                )

        from solver.circulation.exterior_entry import resolve_exterior_entry
        from solver.topology.access import build_realized_connections
        from solver.topology.connection_resolve import resolve_required_connections
        from solver.topology.doors import place_door_openings

        prov = build_solver_provenance(
            generator_strategy=self.strategy_id,
            generator_version=self.generator_version,
            program=program,
        )
        metrics: dict[str, float | int | str | bool] = {
            **provenance_to_metrics(prov),
            "locked_room_count": len(locks.rooms),
            "locked_zone_count": len(locks.zones),
            "stair_locked": locks.stair is not None,
        }
        candidate = LayoutCandidate(
            id=f"candidate-{seed}",
            seed=seed,
            floors=floor_layouts,
            wet_stacks=list(building_zones.wet_stacks),
            zone_placements=zone_placements,
            provenance=prov,
            metrics=metrics,
        )
        candidate.exterior_entry = resolve_exterior_entry(program, candidate)
        from solver.locks.envelopes import build_zone_member_envelopes

        protected = set(locks.locked_room_ids)
        if locks.stair is not None:
            protected.update(
                p.room_id
                for fl in candidate.floors
                for p in fl.placements
                if p.room_id.startswith("stair-")
            )
        zone_envelopes = build_zone_member_envelopes(locks)
        resolve_required_connections(
            program,
            candidate,
            module=module,
            protected_room_ids=protected,
            zone_envelopes=zone_envelopes,
        )
        place_door_openings(program, candidate)
        build_realized_connections(program, candidate)
        return candidate

    @staticmethod
    def _stable_zone_id(
        *,
        locks: LayoutLocks,
        floor_id: str,
        kind: str,
        rect,
        kind_counts: dict[str, int],
    ) -> str:
        """优先复用锁上的 zone_id，保证 Regenerate 后组件 id 稳定。"""
        tol = 1e-4
        for lz in locks.zones_on_floor(floor_id):
            z_kind = lz.zone.value if hasattr(lz.zone, "value") else str(lz.zone)
            if z_kind != kind:
                continue
            if (
                abs(lz.x - rect.x) <= tol
                and abs(lz.y - rect.y) <= tol
                and abs(lz.width - rect.width) <= tol
                and abs(lz.depth - rect.depth) <= tol
                and lz.zone_id
            ):
                return lz.zone_id
        idx = kind_counts.get(kind, 0)
        kind_counts[kind] = idx + 1
        return f"{floor_id}-{kind}-{idx}"

    def _inject_locked_zones(
        self,
        program: DesignProgram,
        locks: LayoutLocks,
        building_zones,
    ) -> None:
        """把锁定分区写入 BuildingZonePlan；room_ids 优先用锁内清单。"""
        if not locks.zones:
            return
        for lz in locks.zones:
            try:
                zone_enum = ArchitecturalZone(lz.zone)
            except ValueError as exc:
                # validate_layout_locks 应已拦截；此处不再静默忽略
                raise ValueError(f"illegal locked zone: {lz.zone!r}") from exc
            if lz.room_ids:
                room_ids = [
                    rid for rid in lz.room_ids if rid not in locks.locked_room_ids
                ]
            else:
                room_ids = [
                    r.id
                    for r in program.rooms_on_floor(lz.floor_id)
                    if r.id not in locks.locked_room_ids
                    and zone_for_room(r) == zone_enum
                ]
            geom = ZoneGeometry(
                zone=zone_enum,
                floor_id=lz.floor_id,
                rect=PlacementRect(
                    x=lz.x, y=lz.y, width=lz.width, depth=lz.depth
                ),
                room_ids=room_ids,
            )
            plan = building_zones.floors.get(lz.floor_id)
            if plan is None:
                plan = FloorZonePlan(floor_id=lz.floor_id, zones=[])
                building_zones.floors[lz.floor_id] = plan
            plan.zones = [z for z in plan.zones if z.zone != zone_enum]
            plan.zones.append(geom)

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
        topology: TopologyPlan,
        access_graph=None,
    ) -> FloorLayout:
        layout_rooms: dict[str, _LayoutRoom] = {
            r.id: _LayoutRoom(spec=r, weight=r.target_area) for r in floor_rooms
        }

        # 按 zone 聚合几何（同 zone 多块 rect）；room_ids 合并
        zone_rects: dict[ArchitecturalZone, list[Rect]] = {}
        zone_room_ids: dict[ArchitecturalZone, list[str]] = {}
        for zg in zone_plan.zones:
            zone_rects.setdefault(zg.zone, []).append(
                Rect(x=zg.rect.x, y=zg.rect.y, width=zg.rect.width, depth=zg.rect.depth)
            )
            bucket = zone_room_ids.setdefault(zg.zone, [])
            for rid in zg.room_ids:
                if rid not in bucket:
                    bucket.append(rid)

        pack_order = topology.pack_order_hint.get(floor.id, [])
        clusters = [
            set(c.room_ids)
            for c in topology.clusters
            if c.floor_id == floor.id
        ]
        # AccessIntent 对作为额外 slicing unit（required 优先共边）
        if access_graph is not None:
            floor_ids = {r.id for r in floor_rooms}
            for conn in access_graph.connections:
                if conn.a in floor_ids and conn.b in floor_ids:
                    clusters.append({conn.a, conn.b})

        # WetStack 锚由 candidate.wet_stacks 承载；本层按 TopologyPlan 序打包
        for zone, room_ids in zone_room_ids.items():
            rects = zone_rects.get(zone, [])
            if not rects or not room_ids:
                continue
            ordered_ids = order_rooms_for_zone(
                room_ids,
                pack_order=pack_order,
                cluster_members=clusters,
            )
            rooms = [
                layout_rooms[rid] for rid in ordered_ids if rid in layout_rooms
            ]
            self._pack_into_rects(
                rooms,
                rects,
                module,
                rng,
                avoid_pairs=topology.avoid_pairs,
                cluster_members=clusters,
            )

        stair_name = "楼梯"
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
        *,
        avoid_pairs=None,
        cluster_members: list[set[str]] | None = None,
    ) -> None:
        if not rooms or not rects:
            return
        if len(rects) == 1:
            r = rects[0]
            self._layout_rooms(
                rooms,
                r.x,
                r.y,
                r.right,
                r.bottom,
                module,
                rng,
                avoid_pairs=avoid_pairs,
                cluster_members=cluster_members,
            )
            return

        total_area = sum(r.area for r in rects) or 1.0
        total_weight = sum(r.weight for r in rooms) or 1.0
        id_to = {lr.spec.id: lr for lr in rooms}
        unit_ids = group_into_slicing_units(
            [lr.spec.id for lr in rooms], cluster_members
        )
        remaining_units: list[list[_LayoutRoom]] = [
            [id_to[rid] for rid in u if rid in id_to] for u in unit_ids
        ]
        remaining_units = [u for u in remaining_units if u]

        for i, rect in enumerate(rects):
            if not remaining_units:
                break
            if i == len(rects) - 1:
                share_units = remaining_units
                remaining_units = []
            else:
                target_w = total_weight * (rect.area / total_area)
                leave = len(rects) - i - 1
                # 尽量留给后续 rect 至少一个 unit；不够则整簇不拆
                max_take = (
                    len(remaining_units)
                    if len(remaining_units) <= leave
                    else len(remaining_units) - leave
                )
                max_take = max(1, max_take)
                cum = 0.0
                split = max_take
                for j, unit in enumerate(remaining_units):
                    cum += sum(lr.weight for lr in unit)
                    if cum >= target_w and j + 1 <= max_take:
                        split = j + 1
                        break
                split = min(split, max_take)
                share_units = remaining_units[:split]
                remaining_units = remaining_units[split:]
            share = [lr for u in share_units for lr in u]
            self._layout_rooms(
                share,
                rect.x,
                rect.y,
                rect.right,
                rect.bottom,
                module,
                rng,
                avoid_pairs=avoid_pairs,
                cluster_members=cluster_members,
            )

    def _layout_rooms(
        self,
        rooms: list[_LayoutRoom],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        module: float,
        rng: random.Random,
        *,
        avoid_pairs=None,
        cluster_members: list[set[str]] | None = None,
    ) -> None:
        if not rooms:
            return
        if len(rooms) == 1:
            rooms[0].rect = PlacementRect(
                x=x0, y=y0, width=max(module, x1 - x0), depth=max(module, y1 - y0)
            )
            return

        unit_ids = group_into_slicing_units(
            [r.spec.id for r in rooms], cluster_members
        )
        # 整组就是一个簇：解锁后按面积再切（簇内允许细分）
        if (
            cluster_members
            and len(unit_ids) == 1
            and len(unit_ids[0]) == len(rooms)
            and len(rooms) > 1
        ):
            self._layout_rooms(
                rooms,
                x0,
                y0,
                x1,
                y1,
                module,
                rng,
                avoid_pairs=avoid_pairs,
                cluster_members=None,
            )
            return

        # avoid 对：优先分到二分两侧（仅一次种子分割）；可能拆簇，属显式分离意图
        avoid_split = None
        if avoid_pairs:
            avoid_split = split_avoid_groups(rooms, avoid_pairs)
        if avoid_split is not None:
            group1, group2 = avoid_split
        elif cluster_members and len(unit_ids) >= 2:
            id_to = {r.spec.id: r for r in rooms}
            units = [[id_to[rid] for rid in u if rid in id_to] for u in unit_ids]
            units = [u for u in units if u]
            parted = bipartition_slicing_units(
                units, weight_of=lambda lr: lr.weight
            )
            if parted is None:
                group1, group2 = rooms[:1], rooms[1:]
            else:
                group1, group2 = parted
        else:
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
            self._layout_rooms(
                group1,
                x0,
                y0,
                cut_x,
                y1,
                module,
                rng,
                avoid_pairs=None,
                cluster_members=cluster_members,
            )
            self._layout_rooms(
                group2,
                cut_x,
                y0,
                x1,
                y1,
                module,
                rng,
                avoid_pairs=None,
                cluster_members=cluster_members,
            )
        else:
            cut_y = snap_value(y0 + height * frac, module)
            cut_y = max(y0 + min_span, min(y1 - min_span, cut_y))
            self._layout_rooms(
                group1,
                x0,
                y0,
                x1,
                cut_y,
                module,
                rng,
                avoid_pairs=None,
                cluster_members=cluster_members,
            )
            self._layout_rooms(
                group2,
                x0,
                cut_y,
                x1,
                y1,
                module,
                rng,
                avoid_pairs=None,
                cluster_members=cluster_members,
            )

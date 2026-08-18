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
from packages.schema.vertical_void import VerticalVoidPlacement
from packages.schema.zoning import ArchitecturalZone, FloorZonePlan, ZoneGeometry

from solver.circulation.stair_core import CorePlacementFailure
from solver.evaluation.weights import DEFAULT_WEIGHTS
from solver.generators.wet_anchor import (
    anchor_floor_id,
    collect_wet_anchor_rects,
    preplace_wet_anchored_rooms,
)
from solver.geometry.buildable import program_pack_rects
from solver.geometry.coverage import (
    LAYOUT_ABSORB_TOLERANCE,
    apply_corridor_access_repair_if_safe,
    assign_residual_gaps_as_circulation,
    clamp_program_room_aspect_ratios,
    clip_placement_away_from_obstacles,
    fill_floor_coverage_gaps,
    grow_rooms_to_min_area,
    largest_aspect_ok_placement_rect,
    resolve_placement_overlaps,
)
from solver.geometry.free_rects import subtract_rects
from solver.geometry.rect import Rect, from_placement, shared_edge_length
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
from solver.vertical.prededuction import build_prededuction_plan

_ASPECT_THRESHOLD = DEFAULT_WEIGHTS.aspect_ratio_threshold


def _rect_aspect(width: float, depth: float) -> float:
    short = min(width, depth)
    long = max(width, depth)
    return long / max(short, 0.01)


def _aspect_ratio_ok(width: float, depth: float, threshold: float = _ASPECT_THRESHOLD) -> bool:
    return _rect_aspect(width, depth) <= threshold + 1e-6


def _placement_aspect_ok(rect: PlacementRect, threshold: float = _ASPECT_THRESHOLD) -> bool:
    return _aspect_ratio_ok(rect.width, rect.depth, threshold)


def _span_bounds_for_aspect(cross_span: float, threshold: float = _ASPECT_THRESHOLD) -> tuple[float, float]:
    """cross × span 矩形满足长宽比时，span 的可行区间。"""
    if cross_span <= 0:
        return 0.0, 0.0
    return cross_span / threshold, cross_span * threshold


def _aspect_cut_bounds(
    start: float,
    end: float,
    cross_span: float,
    *,
    threshold: float = _ASPECT_THRESHOLD,
) -> tuple[float, float]:
    """切分轴上的 cut 坐标区间，使两侧条带均满足长宽比。"""
    span = end - start
    if span <= 1e-9 or cross_span <= 1e-9:
        return start, end
    lo, hi = _span_bounds_for_aspect(cross_span, threshold)
    cut_min = max(start + lo, end - hi)
    cut_max = min(start + hi, end - lo)
    if cut_min > cut_max:
        mid = start + span * 0.5
        return max(start, mid - span * 0.1), min(end, mid + span * 0.1)
    return cut_min, cut_max


def _largest_aspect_ok_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    threshold: float = _ASPECT_THRESHOLD,
) -> PlacementRect:
    return largest_aspect_ok_placement_rect(x0, y0, x1, y1, threshold)


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


def _group_min_area(rooms: list[_LayoutRoom]) -> float:
    return sum(r.spec.resolved_min_area() for r in rooms)


def _group_max_area(rooms: list[_LayoutRoom]) -> float:
    return sum(r.spec.resolved_max_area() for r in rooms)


def _clamp_split_fraction(
    frac: float,
    total_area: float,
    max1: float,
    max2: float,
    min1: float,
    min2: float,
) -> float:
    if total_area <= 0:
        return frac
    lo = max(min1 / total_area, 1.0 - max2 / total_area)
    hi = min(max1 / total_area, 1.0 - min2 / total_area)
    if lo > hi:
        return max(0.0, min(1.0, frac))
    return max(lo, min(hi, frac))


def _clamped_axis_cut(
    start: float,
    end: float,
    frac: float,
    module: float,
    min_area_1: float,
    min_area_2: float,
    cross_span: float,
) -> float:
    """主轴切分：面积下限优先于 min_span，避免对侧被挤成退化条带。"""
    span = end - start
    raw = snap_value(start + span * frac, module)
    if span <= 1e-9 or cross_span <= 1e-9:
        return raw
    area_lo = start + min_area_1 / cross_span
    area_hi = end - min_area_2 / cross_span
    min_span = module * 2
    lo, hi = area_lo, area_hi
    if span + 1e-9 >= 2 * min_span:
        lo = max(lo, start + min_span)
        hi = min(hi, end - min_span)
    if lo > hi + 1e-9:
        lo, hi = area_lo, area_hi
        if lo > hi + 1e-9:
            return max(start, min(end, raw))
    asp_min, asp_max = _aspect_cut_bounds(start, end, cross_span)
    lo = max(lo, asp_min)
    hi = min(hi, asp_max)
    if lo > hi + 1e-9:
        lo, hi = asp_min, asp_max
    cut = max(lo, min(hi, raw))
    eps = min(module, span / 4) if span > 0 else 0.0
    return max(start + eps, min(end - eps, cut))


def _compute_split_fraction(
    group1: list[_LayoutRoom],
    group2: list[_LayoutRoom],
    width: float,
    height: float,
) -> float:
    w1 = sum(r.weight for r in group1)
    w2 = sum(r.weight for r in group2)
    total_w = w1 + w2
    frac = (w1 / total_w) if total_w > 0 else 0.5
    total_area = width * height
    return _clamp_split_fraction(
        frac,
        total_area,
        _group_max_area(group1),
        _group_max_area(group2),
        _group_min_area(group1),
        _group_min_area(group2),
    )


def _placement_rect_area_capped(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    max_area: float,
) -> PlacementRect:
    """在 [x0,y0,x1,y1] 内取面积不超过 max_area 的轴对齐矩形（优先占满宽度）。"""
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    region = w * h
    if region <= max_area + 1e-9:
        return PlacementRect(x=x0, y=y0, width=w, depth=h)
    if w > 0 and max_area / w <= h:
        return PlacementRect(x=x0, y=y0, width=w, depth=max_area / w)
    if h > 0:
        width = max_area / h
        if width <= w:
            return PlacementRect(x=x0, y=y0, width=width, depth=h)
    return PlacementRect(x=x0, y=y0, width=w, depth=h)


def _capped_placement_candidates(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    max_area: float,
) -> list[PlacementRect]:
    """同一 pack 区内多种对齐的 capped 矩形候选。"""
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    region = w * h
    if region <= max_area + 1e-9:
        return [PlacementRect(x=x0, y=y0, width=w, depth=h)]
    out: list[PlacementRect] = []
    if w > 0:
        depth = min(h, max_area / w)
        if depth > 0:
            out.append(PlacementRect(x=x0, y=y0, width=w, depth=depth))
            out.append(PlacementRect(x=x0, y=y1 - depth, width=w, depth=depth))
    if h > 0:
        width = min(w, max_area / h)
        if width > 0:
            out.append(PlacementRect(x=x0, y=y0, width=width, depth=h))
            out.append(PlacementRect(x=x1 - width, y=y0, width=width, depth=h))
    compliant = [c for c in out if _placement_aspect_ok(c)]
    if compliant:
        return compliant
    return out or [_placement_rect_area_capped(x0, y0, x1, y1, max_area)]


def _best_capped_placement(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    max_area: float,
    neighbor_rects: list[Rect],
) -> PlacementRect:
    """选择使剩余碎片与同层其它房间邻接边最大的 capped 放置。"""
    full = Rect(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)
    best: PlacementRect | None = None
    best_score = -1.0
    candidates = _capped_placement_candidates(x0, y0, x1, y1, max_area)
    compliant = [c for c in candidates if _placement_aspect_ok(c)]
    pool = compliant if compliant else candidates
    for cand in pool:
        capped = Rect(x=cand.x, y=cand.y, width=cand.width, depth=cand.depth)
        leftovers = subtract_rects([full], [capped])
        score = 0.0
        for piece in leftovers:
            for neighbor in neighbor_rects:
                score += shared_edge_length(piece, neighbor)
        if score > best_score:
            best_score = score
            best = cand
    return best or _placement_rect_area_capped(x0, y0, x1, y1, max_area)


def _pack_rect_leftovers(pack_rect: Rect, rooms: list[_LayoutRoom]) -> list[Rect]:
    """单房切分后 pack 区内未分配碎片（供同 zone 其它房间吸收）。"""
    if len(rooms) != 1 or rooms[0].rect is None:
        return []
    placed = from_placement(rooms[0].rect)
    leftovers = subtract_rects([pack_rect], [placed])
    return [r for r in leftovers if r.area > 1e-6]


def _trim_and_donate_excess(
    layout_rooms: dict[str, _LayoutRoom],
) -> None:
    """裁切超上限房间，将邻接碎片转给同层尚有容量的其它房间。"""
    from solver.geometry.coverage import try_absorb_sliver_within_area_cap

    for lr in layout_rooms.values():
        if lr.rect is None:
            continue
        max_a = lr.spec.resolved_max_area()
        if lr.rect.area <= max_a + 1e-9:
            continue
        cur = from_placement(lr.rect)
        neighbor_rects = [
            from_placement(other.rect)
            for other in layout_rooms.values()
            if other.rect is not None and other.spec.id != lr.spec.id
        ]
        capped = from_placement(
            _best_capped_placement(
                cur.x,
                cur.y,
                cur.right,
                cur.bottom,
                max_a,
                neighbor_rects,
            )
        )
        leftovers = subtract_rects([cur], [capped])
        lr.rect = PlacementRect(
            x=capped.x,
            y=capped.y,
            width=capped.width,
            depth=capped.depth,
        )
        for piece in leftovers:
            if piece.area <= 1e-6:
                continue
            placed_rects = {
                other.spec.id: from_placement(other.rect)
                for other in layout_rooms.values()
                if other.rect is not None and other.spec.id != lr.spec.id
            }
            best_other: _LayoutRoom | None = None
            best_merged: Rect | None = None
            best_edge = 0.0
            for other in layout_rooms.values():
                if other.spec.id == lr.spec.id or other.rect is None:
                    continue
                other_cur = from_placement(other.rect)
                others = [
                    r
                    for rid, r in placed_rects.items()
                    if rid != other.spec.id
                ]
                merged = try_absorb_sliver_within_area_cap(
                    other_cur,
                    piece,
                    others,
                    other.spec.resolved_max_area(),
                )
                if merged is None:
                    continue
                edge = shared_edge_length(other_cur, piece)
                if edge > best_edge:
                    best_other = other
                    best_merged = merged
                    best_edge = edge
            if best_other is None or best_merged is None:
                continue
            best_other.rect = PlacementRect(
                x=best_merged.x,
                y=best_merged.y,
                width=best_merged.width,
                depth=best_merged.depth,
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
        self._floor_pack_leftovers: list[Rect] = []
        self._current_layout_rooms: dict[str, _LayoutRoom] = {}

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
        pack_rects = program_pack_rects(program)
        locks = locks or LayoutLocks()
        locked_ids = locks.locked_room_ids

        ensure_access_graph(program)
        if topology is None:
            topology = self._topology_planner.plan(program)

        try:
            prededuction = build_prededuction_plan(
                program,
                floor_width=w,
                floor_depth=d,
                snap_module=module,
                rng=rng,
                locks=locks,
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

        core = prededuction.stair_core
        atrium_voids_by_floor = {
            floor.id: prededuction.atrium_placements_on_floor(floor.id)
            for floor in program.floors
        }
        stair_rect = Rect(
            x=core.rect.x,
            y=core.rect.y,
            width=core.rect.width,
            depth=core.rect.depth,
        )
        # WetStack 跨层锚：仅扣楼梯（ATRIUM 按层在 free_rects_by_floor 扣除）
        shared_free = subtract_rects(pack_rects, [stair_rect])

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
            prededuction_holes = prededuction.holes_by_floor.get(floor_id, [])
            holes = _holes_on_floor(floor_id)
            if not holes:
                return subtract_rects(pack_rects, prededuction_holes)
            return subtract_rects(pack_rects, [*prededuction_holes, *holes])

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
        anchor_fid = anchor_floor_id(program)

        floor_layouts_by_id: dict[str, FloorLayout] = {}
        zone_placements: list[ZonePlacement] = []
        wet_anchors: dict[str, Rect] = {}
        floor_order = sorted(
            program.floors,
            key=lambda f: (0 if f.id == anchor_fid else 1, program.floors.index(f)),
        )
        for floor in floor_order:
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
                floor_index=program.floors.index(floor),
                floor_width=w,
                floor_depth=d,
                pack_rects=pack_rects,
                module=module,
                rng=rng,
                topology=topology,
                access_graph=program.access_graph,
                wet_anchors=wet_anchors,
                atrium_voids=atrium_voids_by_floor.get(floor.id, []),
                prededuction_obstacles=prededuction.holes_by_floor.get(floor.id, []),
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
            floor_layouts_by_id[floor.id] = _mirror_wet_stack_onto_floor(
                layout, primary_stack
            )
            if floor.id == anchor_fid:
                wet_anchors = collect_wet_anchor_rects(layout, program)
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

        floor_layouts = [floor_layouts_by_id[f.id] for f in program.floors]

        from solver.circulation.exterior_entry import resolve_exterior_entry
        from solver.topology.access import build_realized_connections
        from solver.topology.connection_resolve import resolve_required_connections
        from solver.topology.doors import place_door_openings
        from solver.topology.windows import place_window_openings

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
            vertical_void_placements=list(prededuction.void_placements),
            zone_placements=zone_placements,
            provenance=prov,
            metrics=metrics,
        )
        candidate.exterior_entry = resolve_exterior_entry(program, candidate)
        entry_ids = frozenset(candidate.exterior_entry.connected_room_ids or [])
        min_by_id = {r.id: r.resolved_min_area() for r in program.rooms}
        candidate = apply_corridor_access_repair_if_safe(
            program,
            candidate,
            pack_rects,
            min_area_by_room_id=min_by_id,
            entry_room_ids=entry_ids,
        )
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
        place_window_openings(program, candidate)
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
        floor_width: float,
        floor_depth: float,
        pack_rects: list[Rect],
        module: float,
        rng: random.Random,
        topology: TopologyPlan,
        access_graph=None,
        wet_anchors: dict[str, Rect] | None = None,
        atrium_voids: list[VerticalVoidPlacement] | None = None,
        prededuction_obstacles: list[Rect] | None = None,
    ) -> FloorLayout:
        layout_rooms: dict[str, _LayoutRoom] = {
            r.id: _LayoutRoom(spec=r, weight=r.target_area) for r in floor_rooms
        }
        self._current_layout_rooms = layout_rooms
        self._floor_pack_leftovers = []

        footprint_bbox = Rect(x=0, y=0, width=floor_width, depth=floor_depth)
        fixed_obstacles = list(prededuction_obstacles or [])
        preplaced = preplace_wet_anchored_rooms(
            floor_rooms,
            footprint=footprint_bbox,
            occupied=fixed_obstacles,
            wet_anchors=wet_anchors or {},
        )
        for rid, placed_rect in preplaced.items():
            if rid in layout_rooms:
                layout_rooms[rid].rect = placed_rect
        preplaced_obstacles = [
            from_placement(lr.rect)
            for lr in layout_rooms.values()
            if lr.rect is not None
        ]
        clip_obstacles = fixed_obstacles + preplaced_obstacles

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

        if clip_obstacles:
            for zone, rects in list(zone_rects.items()):
                clipped: list[Rect] = []
                for zone_rect in rects:
                    clipped.extend(subtract_rects([zone_rect], clip_obstacles))
                zone_rects[zone] = [r for r in clipped if r.area > 1e-6]

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
                layout_rooms[rid]
                for rid in ordered_ids
                if rid in layout_rooms and layout_rooms[rid].rect is None
            ]
            if not rooms:
                continue
            self._pack_into_rects(
                rooms,
                rects,
                module,
                rng,
                avoid_pairs=topology.avoid_pairs,
                cluster_members=clusters,
            )

        if fixed_obstacles:
            for lr in layout_rooms.values():
                if lr.rect is None:
                    continue
                clipped = clip_placement_away_from_obstacles(lr.rect, fixed_obstacles)
                if clipped is not None:
                    lr.rect = clipped

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
        for vp in atrium_voids or []:
            placements.append(
                RoomPlacement(
                    room_id=f"void-{vp.void_id}",
                    floor_id=floor.id,
                    rect=vp.rect.model_copy(),
                    source=PlacementSource.GENERATED,
                    name="天井",
                    category="circulation",
                )
            )
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

        pack_footprint = pack_rects
        min_by_id = {r.id: r.resolved_min_area() for r in floor_rooms}
        max_by_id = {r.id: r.resolved_max_area() for r in floor_rooms}
        placements = fill_floor_coverage_gaps(
            pack_footprint,
            placements,
            extra_gaps=self._floor_pack_leftovers,
            max_area_by_room_id=max_by_id,
            min_area_by_room_id=min_by_id,
        )
        placements = grow_rooms_to_min_area(
            pack_footprint,
            placements,
            min_by_id,
            max_by_id,
        )
        placements = clamp_program_room_aspect_ratios(
            pack_footprint,
            placements,
            floor.id,
            min_area_by_room_id=min_by_id,
        )
        placements = resolve_placement_overlaps(placements)
        placements = fill_floor_coverage_gaps(
            pack_footprint,
            placements,
            max_area_by_room_id=max_by_id,
            min_area_by_room_id=min_by_id,
        )
        placements = resolve_placement_overlaps(placements)
        placements = assign_residual_gaps_as_circulation(
            pack_footprint,
            placements,
            floor.id,
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
            for lr in rooms:
                if lr.rect is not None:
                    for sliver in _pack_rect_leftovers(r, [lr]):
                        self._absorb_sliver_into_zone_room(rooms, sliver)
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
        empty_rects: list[Rect] = []

        if (
            len(remaining_units) == 1
            and len(remaining_units[0]) > 1
            and len(rects) > 1
        ):
            remaining_units = [[lr] for lr in remaining_units[0]]

        if len(remaining_units) <= len(rects):
            order = sorted(range(len(rects)), key=lambda i: rects[i].area, reverse=True)
            for ui, rect_i in enumerate(order[: len(remaining_units)]):
                share = [lr for lr in remaining_units[ui]]
                rect = rects[rect_i]
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
                empty_rects.extend(_pack_rect_leftovers(rect, share))
            for rect_i in order[len(remaining_units) :]:
                empty_rects.append(rects[rect_i])
            for sliver in empty_rects:
                self._absorb_sliver_into_zone_room(rooms, sliver)
            return

        for i, rect in enumerate(rects):
            if i == len(rects) - 1:
                share_units = remaining_units
                remaining_units = []
            elif not remaining_units:
                empty_rects.append(rect)
                continue
            else:
                target_w = total_weight * (rect.area / total_area)
                leave = len(rects) - i - 1
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
            if not share:
                empty_rects.append(rect)
                continue
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
            empty_rects.extend(_pack_rect_leftovers(rect, share))

        for sliver in empty_rects:
            self._absorb_sliver_into_zone_room(rooms, sliver)

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
            lr = rooms[0]
            cw = max(0.0, x1 - x0)
            ch = max(0.0, y1 - y0)
            max_a = lr.spec.resolved_max_area()
            region = cw * ch
            if region > max_a + 1e-9:
                neighbor_rects = [
                    from_placement(other.rect)
                    for other in self._current_layout_rooms.values()
                    if other.rect is not None and other.spec.id != lr.spec.id
                ]
                capped = _best_capped_placement(
                    x0, y0, x1, y1, max_a, neighbor_rects
                )
                lr.rect = capped
                full = Rect(x=x0, y=y0, width=cw, depth=ch)
                capped_r = Rect(
                    x=capped.x,
                    y=capped.y,
                    width=capped.width,
                    depth=capped.depth,
                )
                self._floor_pack_leftovers.extend(
                    subtract_rects([full], [capped_r])
                )
            else:
                placed = _largest_aspect_ok_rect(x0, y0, x1, y1)
                lr.rect = placed
                full = Rect(x=x0, y=y0, width=cw, depth=ch)
                placed_r = Rect(
                    x=placed.x,
                    y=placed.y,
                    width=placed.width,
                    depth=placed.depth,
                )
                if placed_r.area + 1e-9 < full.area:
                    self._floor_pack_leftovers.extend(
                        subtract_rects([full], [placed_r])
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

        width = x1 - x0
        height = y1 - y0
        frac = _compute_split_fraction(group1, group2, width, height)

        if abs(width - height) < 1e-6:
            split_horizontal = rng.random() < 0.5
        else:
            split_horizontal = width >= height

        if split_horizontal:
            cut_x = _clamped_axis_cut(
                x0,
                x1,
                frac,
                module,
                _group_min_area(group1),
                _group_min_area(group2),
                height,
            )
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
            cut_y = _clamped_axis_cut(
                y0,
                y1,
                frac,
                module,
                _group_min_area(group1),
                _group_min_area(group2),
                width,
            )
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

    def _absorb_sliver_into_zone_room(
        self, rooms: list[_LayoutRoom], sliver: Rect
    ) -> None:
        from solver.geometry.coverage import try_absorb_sliver_within_area_cap

        placed = [lr for lr in rooms if lr.rect is not None]
        if not placed:
            return
        placed_rects = [from_placement(lr.rect) for lr in placed]
        pairs = list(zip(placed, placed_rects, strict=True))
        undersized = [
            (lr, cur)
            for lr, cur in pairs
            if lr.rect.area + 1e-9 < lr.spec.resolved_min_area()
        ]

        def _pick(candidates: list[tuple[_LayoutRoom, Rect]]) -> tuple[_LayoutRoom, Rect] | None:
            best_lr: _LayoutRoom | None = None
            best_rect: Rect | None = None
            best_edge = 0.0
            for lr, cur in candidates:
                if lr.rect.area >= lr.spec.resolved_max_area() - 1e-9:
                    continue
                others = [r for r in placed_rects if r is not cur]
                merged = try_absorb_sliver_within_area_cap(
                    cur,
                    sliver,
                    others,
                    lr.spec.resolved_max_area(),
                    tolerance=LAYOUT_ABSORB_TOLERANCE,
                )
                if merged is None:
                    continue
                if not _aspect_ratio_ok(merged.width, merged.depth):
                    continue
                edge = shared_edge_length(cur, sliver)
                if edge > best_edge:
                    best_lr = lr
                    best_rect = merged
                    best_edge = edge
            if best_lr is None or best_rect is None:
                return None
            return best_lr, best_rect

        picked = _pick(undersized) if undersized else None
        if picked is None:
            picked = _pick(pairs)
        if picked is None:
            return
        best_lr, best_rect = picked
        best_lr.rect = PlacementRect(
            x=best_rect.x,
            y=best_rect.y,
            width=best_rect.width,
            depth=best_rect.depth,
        )

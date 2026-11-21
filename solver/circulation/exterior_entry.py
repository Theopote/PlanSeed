"""
ExteriorEntry 解析 — Entrance ≠ Stair。

边优先级：ExteriorEntrySpec.preferred_edge → SiteSpec.entrance_edge
→ road_edges[0] → 默认 SOUTH。

入口只建立到**一个**物理落位房间的 EXTERIOR_ENTRY：
在选定边上按门厅>客厅>…排序，把入口线段吸附到首选房间外墙，
``connected_room_ids`` 仅含开口真正落在其边界上的房间（通常一个）。
其它贴边房间不得凭「同侧」获得虚假入口边。
"""

from __future__ import annotations

from packages.schema.entry import ExteriorEntryPlacement, ExteriorEntrySpec
from packages.schema.layout import LayoutCandidate, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.site import CardinalEdge

from solver.evaluation.orientation import exterior_world_orientations
from solver.geometry.rect import Rect, from_placement, program_local_buildable
from solver.geometry.site_coords import SiteCoordinateSystem

_ENTRY_CATEGORY_RANK = {
    "circulation": 2,
    "public": 0,
    "wet": 3,
    "private": 4,
    "service": 5,
    "other": 3,
}

_EDGE_EPS = 1e-6


def _is_stair(p: RoomPlacement) -> bool:
    return p.room_id.startswith("stair-") or (
        p.category == "circulation" and p.name is not None and "楼梯" in p.name
    )


def resolve_entry_edge(
    program: DesignProgram,
    spec: ExteriorEntrySpec | None = None,
) -> CardinalEdge:
    """
    入口边解析：
    preferred_edge → entrance_edge → road_edges[0] → SOUTH
    """
    if spec is None:
        spec = getattr(program, "exterior_entry_spec", None)
    if spec is not None and spec.preferred_edge is not None:
        return spec.preferred_edge
    site = program.site
    if site.entrance_edge is not None:
        return site.entrance_edge
    roads = list(site.road_edges or [])
    if roads:
        return roads[0]
    return CardinalEdge.SOUTH


def resolve_exterior_entry(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    entry_width: float | None = None,
    spec: ExteriorEntrySpec | None = None,
) -> ExteriorEntryPlacement:
    """在选定边上放置入口，并只连接开口真正落在边界上的房间。"""
    spec = spec or getattr(program, "exterior_entry_spec", None) or ExteriorEntrySpec()
    edge = resolve_entry_edge(program, spec)
    width = entry_width if entry_width is not None else spec.width
    road = list(program.site.road_edges or [])
    on_road = edge in road

    buildable = program_local_buildable(program)
    ground = candidate.floors[0].floor_id if candidate.floors else "F1"

    cs = SiteCoordinateSystem(getattr(program.site, "north_angle", 0.0) or 0.0)
    edge_val = edge.value

    touching: list[RoomPlacement] = []
    if candidate.floors:
        for p in candidate.floors[0].placements:
            worlds = exterior_world_orientations(
                from_placement(p.rect), buildable, cs
            )
            if edge_val in worlds:
                touching.append(p)

    from solver.semantics.roles import is_foyer, is_living

    foyer_ids = {r.id for r in program.rooms if is_foyer(r)}
    living_ids = {r.id for r in program.rooms if is_living(r)}

    def rank(p: RoomPlacement) -> tuple[int, int, int, str]:
        stair_pen = 10 if _is_stair(p) else 0
        foyer_pen = 0 if p.room_id in foyer_ids else (1 if p.room_id in living_ids else 2)
        cat = (p.category or "other").lower()
        return (stair_pen, foyer_pen, _ENTRY_CATEGORY_RANK.get(cat, 5), p.room_id)

    ranked = sorted(touching, key=rank)
    if not ranked and candidate.floors:
        any_ext: list[RoomPlacement] = []
        for p in candidate.floors[0].placements:
            worlds = exterior_world_orientations(
                from_placement(p.rect), buildable, cs
            )
            if worlds:
                any_ext.append(p)
        ranked = sorted(any_ext, key=rank)

    cx, cy = _point_on_buildable_edge(buildable, edge)
    connected: list[str] = []
    if ranked:
        primary = ranked[0]
        cx, cy = _snap_entry_to_room_edge(
            from_placement(primary.rect), edge, width, buildable
        )
        # 唯一物理入口房间（同侧贴边不等于入口连通）
        connected = [primary.room_id]

    return ExteriorEntryPlacement(
        id=spec.id,
        edge=edge,
        floor_id=ground,
        x=cx,
        y=cy,
        width=width,
        on_road_edge=on_road,
        connected_room_ids=connected,
    )


def _point_on_buildable_edge(buildable: Rect, edge: CardinalEdge) -> tuple[float, float]:
    mid_x = buildable.x + buildable.width / 2
    mid_y = buildable.y + buildable.depth / 2
    if edge == CardinalEdge.NORTH:
        return mid_x, buildable.top
    if edge == CardinalEdge.SOUTH:
        return mid_x, buildable.bottom
    if edge == CardinalEdge.WEST:
        return buildable.left, mid_y
    return buildable.right, mid_y


def _snap_entry_to_room_edge(
    room: Rect,
    edge: CardinalEdge,
    width: float,
    buildable: Rect,
) -> tuple[float, float]:
    """把入口中心吸附到房间朝向 ``edge`` 的外墙中段，并夹在 buildable 内。"""
    half = max(width, 0.1) / 2
    if edge == CardinalEdge.SOUTH:
        lo = max(room.left + half, buildable.left + half)
        hi = min(room.right - half, buildable.right - half)
        x = (lo + hi) / 2 if lo <= hi else (room.left + room.right) / 2
        return x, room.bottom
    if edge == CardinalEdge.NORTH:
        lo = max(room.left + half, buildable.left + half)
        hi = min(room.right - half, buildable.right - half)
        x = (lo + hi) / 2 if lo <= hi else (room.left + room.right) / 2
        return x, room.top
    if edge == CardinalEdge.WEST:
        lo = max(room.bottom + half, buildable.bottom + half)
        hi = min(room.top - half, buildable.top - half)
        y = (lo + hi) / 2 if lo <= hi else (room.bottom + room.top) / 2
        return room.left, y
    lo = max(room.bottom + half, buildable.bottom + half)
    hi = min(room.top - half, buildable.top - half)
    y = (lo + hi) / 2 if lo <= hi else (room.bottom + room.top) / 2
    return room.right, y


def _entry_opening_on_room(
    room: Rect,
    edge: CardinalEdge,
    cx: float,
    cy: float,
    width: float,
) -> bool:
    """入口线段（中心+宽度）是否落在房间该侧外墙上。"""
    half = max(width, 0.1) / 2
    if edge == CardinalEdge.SOUTH:
        if abs(cy - room.bottom) > _EDGE_EPS:
            return False
        a, b = cx - half, cx + half
        return b > room.left + _EDGE_EPS and a < room.right - _EDGE_EPS
    if edge == CardinalEdge.NORTH:
        if abs(cy - room.top) > _EDGE_EPS:
            return False
        a, b = cx - half, cx + half
        return b > room.left + _EDGE_EPS and a < room.right - _EDGE_EPS
    if edge == CardinalEdge.WEST:
        if abs(cx - room.left) > _EDGE_EPS:
            return False
        a, b = cy - half, cy + half
        return b > room.bottom + _EDGE_EPS and a < room.top - _EDGE_EPS
    if abs(cx - room.right) > _EDGE_EPS:
        return False
    a, b = cy - half, cy + half
    return b > room.bottom + _EDGE_EPS and a < room.top - _EDGE_EPS

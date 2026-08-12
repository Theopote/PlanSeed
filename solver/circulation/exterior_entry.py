"""
ExteriorEntry 解析 — Entrance ≠ Stair。

边优先级：ExteriorEntrySpec.preferred_edge → SiteSpec.entrance_edge
→ road_edges[0] → 默认 SOUTH。
入口优先连厅/门厅，不把楼梯当入口。
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
    """在选定边上放置 ExteriorEntryPlacement，并列出贴边房间（排除楼梯优先）。"""
    spec = spec or getattr(program, "exterior_entry_spec", None) or ExteriorEntrySpec()
    edge = resolve_entry_edge(program, spec)
    width = entry_width if entry_width is not None else spec.width
    road = list(program.site.road_edges or [])
    on_road = edge in road

    buildable = program_local_buildable(program)
    cx, cy = _point_on_buildable_edge(buildable, edge)
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

    def rank(p: RoomPlacement) -> tuple[int, int, str]:
        stair_pen = 10 if _is_stair(p) else 0
        cat = (p.category or "other").lower()
        return (stair_pen, _ENTRY_CATEGORY_RANK.get(cat, 5), p.room_id)

    connected = [p.room_id for p in sorted(touching, key=rank)]

    if not connected and candidate.floors:
        any_ext: list[RoomPlacement] = []
        for p in candidate.floors[0].placements:
            worlds = exterior_world_orientations(
                from_placement(p.rect), buildable, cs
            )
            if worlds:
                any_ext.append(p)
        connected = [p.room_id for p in sorted(any_ext, key=rank)]

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

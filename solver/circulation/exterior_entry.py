"""
ExteriorEntry 解析 — Entrance ≠ Stair。

入口贴 buildable 外缘（SiteSpec.entrance_edge），优先连厅/门厅，不把楼梯当入口。
"""

from __future__ import annotations

from packages.schema.entry import ExteriorEntry
from packages.schema.layout import LayoutCandidate, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.site import CardinalEdge
from solver.evaluation.orientation import exterior_world_orientations
from solver.geometry.rect import Rect, from_placement
from solver.geometry.site_coords import SiteCoordinateSystem

# 入口优先连接的房间类别（厅 / 门厅 / 公共），楼梯垫底
_ENTRY_CATEGORY_RANK = {
    "circulation": 2,  # foyer/hall 若标 circulation
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


def resolve_exterior_entry(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    entry_width: float = 1.2,
) -> ExteriorEntry:
    """
    在 entrance_edge 上放置 ExteriorEntry，并列出贴边相连房间（排除楼梯优先）。
    """
    edge = program.site.entrance_edge
    road = list(program.site.road_edges or [])
    on_road = edge in road
    # 若指定了临路且入口不在临路：仍用 entrance_edge，但标记 on_road=False
    # 未来可 soft 提示应对齐 road_edges

    buildable = Rect(
        x=program.buildable.x,
        y=program.buildable.y,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )
    cx, cy = _point_on_buildable_edge(buildable, edge)
    ground = candidate.floors[0].floor_id if candidate.floors else "F1"

    cs = SiteCoordinateSystem(getattr(program.site, "north_angle", 0.0) or 0.0)
    edge_val = edge.value if isinstance(edge, CardinalEdge) else str(edge)

    touching: list[RoomPlacement] = []
    if candidate.floors:
        for p in candidate.floors[0].placements:
            worlds = exterior_world_orientations(
                from_placement(p.rect), buildable, cs
            )
            if edge_val in worlds:
                touching.append(p)

    # 排序：非楼梯优先，再按类别
    def rank(p: RoomPlacement) -> tuple[int, int, str]:
        stair_pen = 10 if _is_stair(p) else 0
        cat = (p.category or "other").lower()
        return (stair_pen, _ENTRY_CATEGORY_RANK.get(cat, 5), p.room_id)

    touching_sorted = sorted(touching, key=rank)
    connected = [p.room_id for p in touching_sorted]

    # 回退：入口边无贴房时，取地面层任意外墙房间（仍排除楼梯优先）
    if not connected and candidate.floors:
        any_ext: list[RoomPlacement] = []
        for p in candidate.floors[0].placements:
            worlds = exterior_world_orientations(
                from_placement(p.rect), buildable, cs
            )
            if worlds:
                any_ext.append(p)
        connected = [p.room_id for p in sorted(any_ext, key=rank)]

    return ExteriorEntry(
        id="exterior-entry",
        edge=edge if isinstance(edge, CardinalEdge) else CardinalEdge(edge_val),
        floor_id=ground,
        x=cx,
        y=cy,
        width=entry_width,
        on_road_edge=on_road,
        connected_room_ids=connected,
    )


def _point_on_buildable_edge(buildable: Rect, edge: CardinalEdge) -> tuple[float, float]:
    """入口中心落在 buildable 对应边中点（模型坐标）。"""
    mid_x = buildable.x + buildable.width / 2
    mid_y = buildable.y + buildable.depth / 2
    if edge == CardinalEdge.NORTH:
        return mid_x, buildable.top
    if edge == CardinalEdge.SOUTH:
        return mid_x, buildable.bottom
    if edge == CardinalEdge.WEST:
        return buildable.left, mid_y
    return buildable.right, mid_y

"""入口公区预放置 — 把门厅/客厅贴到入口 model 边，提升 entry_to_public。

仅一层（调用方保证）；有门厅优先，否则同层客厅。失败则返回空，回退原打包。
"""

from __future__ import annotations

from packages.schema.layout import PlacementRect
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge

from solver.geometry.free_rects import subtract_rects
from solver.geometry.rect import Rect, from_placement
from solver.semantics.roles import is_foyer, is_living

_MIN_STRIP = 1.8
_MAX_STRIP = 4.5
_EDGE_EPS = 1e-6


def select_entry_anchor_room(
    rooms: list[RoomSpec],
    *,
    foyer_only: bool = True,
) -> RoomSpec | None:
    """
    入口预放置目标：默认仅门厅（面积小、专司入户）。

    客厅过大，条带预放会掏空 DAY 区导致 valid 崩塌；无门厅时交给分区偏置即可。
    """
    foyers = sorted((r for r in rooms if is_foyer(r)), key=lambda r: r.id)
    if foyers:
        return foyers[0]
    if foyer_only:
        return None
    livings = sorted(
        (
            r
            for r in rooms
            if is_living(r) and r.category == RoomCategory.PUBLIC
        ),
        key=lambda r: r.id,
    )
    return livings[0] if livings else None


def _rects_touching_edge(free: list[Rect], edge: CardinalEdge, footprint: Rect) -> list[Rect]:
    out: list[Rect] = []
    for r in free:
        if edge == CardinalEdge.WEST and abs(r.left - footprint.left) <= _EDGE_EPS:
            out.append(r)
        elif edge == CardinalEdge.EAST and abs(r.right - footprint.right) <= _EDGE_EPS:
            out.append(r)
        elif edge == CardinalEdge.NORTH and abs(r.top - footprint.top) <= _EDGE_EPS:
            out.append(r)
        elif edge == CardinalEdge.SOUTH and abs(r.bottom - footprint.bottom) <= _EDGE_EPS:
            out.append(r)
    out.sort(key=lambda r: r.area, reverse=True)
    return out


def _strip_in_region(
    region: Rect,
    edge: CardinalEdge,
    *,
    target_area: float,
    min_area: float,
    max_area: float,
) -> PlacementRect | None:
    """在贴边 region 内切一条入口进深带，面积夹在 [min,max]。"""
    area = min(max(target_area, min_area), max_area, region.area)
    if area + 1e-9 < min_area:
        return None

    if edge in (CardinalEdge.WEST, CardinalEdge.EAST):
        span = region.depth
        if span <= _EDGE_EPS:
            return None
        depth = area / span
        depth = max(_MIN_STRIP, min(_MAX_STRIP, depth, region.width))
        # 若夹深后面积仍不够，拉长占用整段
        if depth * span + 1e-9 < min_area:
            depth = min(region.width, max(depth, min_area / span))
        depth = min(depth, region.width)
        height = min(span, max(area / depth, min_area / depth))
        height = min(height, region.depth)
        y = region.y + (region.depth - height) / 2
        if edge == CardinalEdge.WEST:
            x = region.x
        else:
            x = region.right - depth
        if depth * height + 1e-9 < min_area:
            return None
        return PlacementRect(x=x, y=y, width=depth, depth=height)

    span = region.width
    if span <= _EDGE_EPS:
        return None
    depth = area / span
    depth = max(_MIN_STRIP, min(_MAX_STRIP, depth, region.depth))
    if depth * span + 1e-9 < min_area:
        depth = min(region.depth, max(depth, min_area / span))
    depth = min(depth, region.depth)
    width = min(span, max(area / depth, min_area / depth))
    width = min(width, region.width)
    x = region.x + (region.width - width) / 2
    if edge == CardinalEdge.NORTH:
        y = region.y
    else:
        y = region.bottom - depth
    if width * depth + 1e-9 < min_area:
        return None
    return PlacementRect(x=x, y=y, width=width, depth=depth)


def _touches_footprint_edge(
    rect: Rect, footprint: Rect, edge: CardinalEdge
) -> bool:
    if edge == CardinalEdge.WEST:
        return abs(rect.left - footprint.left) <= _EDGE_EPS
    if edge == CardinalEdge.EAST:
        return abs(rect.right - footprint.right) <= _EDGE_EPS
    if edge == CardinalEdge.NORTH:
        return abs(rect.top - footprint.top) <= _EDGE_EPS
    if edge == CardinalEdge.SOUTH:
        return abs(rect.bottom - footprint.bottom) <= _EDGE_EPS
    return False


def preplace_entry_anchor_room(
    rooms: list[RoomSpec],
    *,
    footprint: Rect,
    occupied: list[Rect],
    model_edge: CardinalEdge,
    pack_regions: list[Rect] | None = None,
) -> dict[str, PlacementRect]:
    """
    把入口公区房间预贴到入口 model 边。

    ``pack_regions`` 若给定（通常为 DAY 区矩形），只在这些区域内落位，
    避免切掉车库等其它功能区导致面积爆表。贴边判定仍相对整层 ``footprint``。
    """
    room = select_entry_anchor_room(rooms)
    if room is None:
        return {}

    regions = list(pack_regions) if pack_regions is not None else [footprint]
    if not regions:
        return {}
    free = subtract_rects(regions, occupied)
    if not free:
        return {}
    touching = _rects_touching_edge(free, model_edge, footprint)
    if not touching:
        return {}

    min_a = room.resolved_min_area()
    max_a = room.resolved_max_area()
    target = room.target_area
    for region in touching:
        placed = _strip_in_region(
            region,
            model_edge,
            target_area=target,
            min_area=min_a,
            max_area=max_a,
        )
        if placed is None:
            continue
        rect = from_placement(placed)
        if not _touches_footprint_edge(rect, footprint, model_edge):
            continue
        return {room.id: placed}
    return {}

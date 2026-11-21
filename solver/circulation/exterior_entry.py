"""
ExteriorEntry 解析 — Entrance ≠ Stair。

边优先级：ExteriorEntrySpec.preferred_edge → SiteSpec.entrance_edge
→ road_edges[0] → 默认 SOUTH。

``entrance_edge`` / ``road_edges`` 语义为**世界方位**（与朝向评价一致）。
选房与吸附统一用 ``SiteCoordinateSystem`` 把世界方位换成 **model 边**，
再落到该 model 外墙上。入口只连接一个物理落位房间。
"""

from __future__ import annotations

from packages.schema.entry import ExteriorEntryPlacement, ExteriorEntrySpec
from packages.schema.layout import LayoutCandidate, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.site import CardinalEdge, CardinalOrientation

from solver.geometry.exterior import (
    ExteriorWallSegment,
    program_exterior_segments,
)
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
_ALL_WORLD = (
    CardinalOrientation.SOUTH,
    CardinalOrientation.NORTH,
    CardinalOrientation.EAST,
    CardinalOrientation.WEST,
)


def _is_stair(p: RoomPlacement) -> bool:
    return p.room_id.startswith("stair-") or (
        p.category == "circulation" and p.name is not None and "楼梯" in p.name
    )


def resolve_entry_edge(
    program: DesignProgram,
    spec: ExteriorEntrySpec | None = None,
) -> CardinalEdge:
    """
    入口**世界方位**解析：
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


def _as_world(edge: CardinalEdge | CardinalOrientation | str) -> CardinalOrientation:
    val = edge.value if hasattr(edge, "value") else str(edge).lower()
    return CardinalOrientation(val)


def _as_model_edge(name: str) -> CardinalEdge:
    return CardinalEdge(name)


def resolve_exterior_entry(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    entry_width: float | None = None,
    spec: ExteriorEntrySpec | None = None,
) -> ExteriorEntryPlacement:
    """按世界方位选边，在对应 model 外墙上放置唯一入口。"""
    spec = spec or getattr(program, "exterior_entry_spec", None) or ExteriorEntrySpec()
    preferred_world = _as_world(resolve_entry_edge(program, spec))
    width = entry_width if entry_width is not None else spec.width
    road_worlds = {_as_world(e) for e in (program.site.road_edges or [])}

    buildable = program_local_buildable(program)
    ground = candidate.floors[0].floor_id if candidate.floors else "F1"
    cs = SiteCoordinateSystem.from_site(program.site)

    from solver.semantics.roles import is_foyer, is_living

    foyer_ids = {r.id for r in program.rooms if is_foyer(r)}
    living_ids = {r.id for r in program.rooms if is_living(r)}

    def rank(p: RoomPlacement) -> tuple[int, int, int, str]:
        stair_pen = 10 if _is_stair(p) else 0
        foyer_pen = 0 if p.room_id in foyer_ids else (1 if p.room_id in living_ids else 2)
        cat = (p.category or "other").lower()
        return (stair_pen, foyer_pen, _ENTRY_CATEGORY_RANK.get(cat, 5), p.room_id)

    ground_placements: list[RoomPlacement] = (
        list(candidate.floors[0].placements) if candidate.floors else []
    )

    def rooms_on_world(
        world: CardinalOrientation,
    ) -> list[tuple[RoomPlacement, ExteriorWallSegment]]:
        """返回 (placement, 真实外墙段) 贴靠朝向 ``world`` 的外墙。"""
        wanted = cs.model_edges_facing(world)
        out: list[tuple[RoomPlacement, ExteriorWallSegment]] = []
        for p in ground_placements:
            rect = from_placement(p.rect)
            for seg in program_exterior_segments(rect, program):
                if seg.direction in wanted and seg.can_fit(width):
                    out.append((p, seg))
        return out

    # 1) 首选世界方位；2) 临路其它方位；3) 任意有外墙方位（并改写实际朝向）
    search_worlds: list[CardinalOrientation] = [preferred_world]
    for w in _ALL_WORLD:
        if w not in search_worlds and w in road_worlds:
            search_worlds.append(w)
    for w in _ALL_WORLD:
        if w not in search_worlds:
            search_worlds.append(w)

    chosen_world = preferred_world
    primary: RoomPlacement | None = None
    chosen_seg: ExteriorWallSegment | None = None

    for world in search_worlds:
        hits = rooms_on_world(world)
        if not hits:
            continue
        # 房间优先级 → 更长可落位墙段
        hits_sorted = sorted(
            hits, key=lambda t: (*rank(t[0]), -t[1].length)
        )
        primary, chosen_seg = hits_sorted[0]
        chosen_world = world
        break

    model_edge = (
        _as_model_edge(chosen_seg.direction)
        if chosen_seg is not None
        else _as_model_edge(
            next(iter(cs.model_edges_facing(preferred_world)), preferred_world.value)
        )
    )

    cx, cy = _point_on_buildable_model_edge(buildable, model_edge)
    connected: list[str] = []
    if primary is not None and chosen_seg is not None:
        cx, cy = _snap_entry_to_segment(chosen_seg, width)
        if _entry_opening_on_segment(chosen_seg, cx, cy, width):
            connected = [primary.room_id]
        else:
            connected = []

    on_road = bool(
        connected
        and chosen_world in road_worlds
        and _opening_on_buildable_exterior(buildable, model_edge, cx, cy, width)
    )

    return ExteriorEntryPlacement(
        id=spec.id,
        edge=model_edge,
        floor_id=ground,
        x=cx,
        y=cy,
        width=width,
        on_road_edge=on_road,
        connected_room_ids=connected,
    )


def _point_on_buildable_model_edge(
    buildable: Rect, edge: CardinalEdge
) -> tuple[float, float]:
    mid_x = buildable.x + buildable.width / 2
    mid_y = buildable.y + buildable.depth / 2
    if edge == CardinalEdge.NORTH:
        return mid_x, buildable.top
    if edge == CardinalEdge.SOUTH:
        return mid_x, buildable.bottom
    if edge == CardinalEdge.WEST:
        return buildable.left, mid_y
    return buildable.right, mid_y


def _snap_entry_to_segment(
    seg: ExteriorWallSegment,
    width: float,
) -> tuple[float, float]:
    """把入口中心吸附到真实外墙段中点（保证开口落在段内）。"""
    half = max(width, 0.1) / 2
    if seg.axis == "x":
        lo = min(seg.x0, seg.x1) + half
        hi = max(seg.x0, seg.x1) - half
        x = (lo + hi) / 2 if lo <= hi else seg.mid_x
        return x, seg.mid_y
    lo = min(seg.y0, seg.y1) + half
    hi = max(seg.y0, seg.y1) - half
    y = (lo + hi) / 2 if lo <= hi else seg.mid_y
    return seg.mid_x, y


def _entry_opening_on_segment(
    seg: ExteriorWallSegment,
    cx: float,
    cy: float,
    width: float,
) -> bool:
    """入口线段是否完整落在真实外墙段上。"""
    half = max(width, 0.1) / 2
    if seg.axis == "x":
        if abs(cy - seg.mid_y) > _EDGE_EPS:
            return False
        a, b = cx - half, cx + half
        lo, hi = sorted((seg.x0, seg.x1))
        return a >= lo - _EDGE_EPS and b <= hi + _EDGE_EPS
    if abs(cx - seg.mid_x) > _EDGE_EPS:
        return False
    a, b = cy - half, cy + half
    lo, hi = sorted((seg.y0, seg.y1))
    return a >= lo - _EDGE_EPS and b <= hi + _EDGE_EPS


def _opening_on_buildable_exterior(
    buildable: Rect,
    model_edge: CardinalEdge,
    cx: float,
    cy: float,
    width: float,
) -> bool:
    """开口中心是否贴在可建区对应 model 外缘上。"""
    half = max(width, 0.1) / 2
    if model_edge == CardinalEdge.SOUTH:
        return abs(cy - buildable.bottom) <= _EDGE_EPS and (
            cx - half >= buildable.left - _EDGE_EPS
            and cx + half <= buildable.right + _EDGE_EPS
        )
    if model_edge == CardinalEdge.NORTH:
        return abs(cy - buildable.top) <= _EDGE_EPS and (
            cx - half >= buildable.left - _EDGE_EPS
            and cx + half <= buildable.right + _EDGE_EPS
        )
    if model_edge == CardinalEdge.WEST:
        return abs(cx - buildable.left) <= _EDGE_EPS and (
            cy - half >= buildable.top - _EDGE_EPS
            and cy + half <= buildable.bottom + _EDGE_EPS
        )
    return abs(cx - buildable.right) <= _EDGE_EPS and (
        cy - half >= buildable.top - _EDGE_EPS
        and cy + half <= buildable.bottom + _EDGE_EPS
    )

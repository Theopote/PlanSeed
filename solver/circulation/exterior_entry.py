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

from solver.evaluation.orientation import exterior_model_edges
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
    ) -> list[tuple[RoomPlacement, str]]:
        """返回 (placement, model_edge) 贴靠朝向 ``world`` 的外墙。"""
        wanted = cs.model_edges_facing(world)
        out: list[tuple[RoomPlacement, str]] = []
        for p in ground_placements:
            rect = from_placement(p.rect)
            model = exterior_model_edges(rect, buildable)
            for me in sorted(model & wanted):
                out.append((p, me))
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
    model_edge_name: str | None = None

    for world in search_worlds:
        hits = rooms_on_world(world)
        if not hits:
            continue
        hits_sorted = sorted(hits, key=lambda t: rank(t[0]))
        primary, model_edge_name = hits_sorted[0]
        chosen_world = world
        break

    model_edge = (
        _as_model_edge(model_edge_name)
        if model_edge_name is not None
        else _as_model_edge(
            next(iter(cs.model_edges_facing(preferred_world)), preferred_world.value)
        )
    )

    cx, cy = _point_on_buildable_model_edge(buildable, model_edge)
    connected: list[str] = []
    if primary is not None:
        room_rect = from_placement(primary.rect)
        cx, cy = _snap_entry_to_room_edge(room_rect, model_edge, width, buildable)
        if _entry_opening_on_room(room_rect, model_edge, cx, cy, width):
            connected = [primary.room_id]
        else:
            # 吸附失败则不建立虚假 EXTERIOR_ENTRY
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


def _snap_entry_to_room_edge(
    room: Rect,
    model_edge: CardinalEdge,
    width: float,
    buildable: Rect,
) -> tuple[float, float]:
    """把入口中心吸附到房间的 **model** 外墙中段。"""
    half = max(width, 0.1) / 2
    if model_edge == CardinalEdge.SOUTH:
        lo = max(room.left + half, buildable.left + half)
        hi = min(room.right - half, buildable.right - half)
        x = (lo + hi) / 2 if lo <= hi else (room.left + room.right) / 2
        return x, room.bottom
    if model_edge == CardinalEdge.NORTH:
        lo = max(room.left + half, buildable.left + half)
        hi = min(room.right - half, buildable.right - half)
        x = (lo + hi) / 2 if lo <= hi else (room.left + room.right) / 2
        return x, room.top
    if model_edge == CardinalEdge.WEST:
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
    model_edge: CardinalEdge,
    cx: float,
    cy: float,
    width: float,
) -> bool:
    """入口线段是否完整落在房间该 model 外墙上。"""
    half = max(width, 0.1) / 2
    if model_edge == CardinalEdge.SOUTH:
        if abs(cy - room.bottom) > _EDGE_EPS:
            return False
        a, b = cx - half, cx + half
        return a >= room.left - _EDGE_EPS and b <= room.right + _EDGE_EPS
    if model_edge == CardinalEdge.NORTH:
        if abs(cy - room.top) > _EDGE_EPS:
            return False
        a, b = cx - half, cx + half
        return a >= room.left - _EDGE_EPS and b <= room.right + _EDGE_EPS
    if model_edge == CardinalEdge.WEST:
        if abs(cx - room.left) > _EDGE_EPS:
            return False
        a, b = cy - half, cy + half
        return a >= room.top - _EDGE_EPS and b <= room.bottom + _EDGE_EPS
    if abs(cx - room.right) > _EDGE_EPS:
        return False
    a, b = cy - half, cy + half
    return a >= room.top - _EDGE_EPS and b <= room.bottom + _EDGE_EPS


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

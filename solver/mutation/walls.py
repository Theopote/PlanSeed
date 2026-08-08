"""共墙枚举与几何推导 — Phase 4.3.1 有限墙编辑。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from packages.schema.layout import PlacementRect
from solver.geometry.rect import from_placement, shared_edge_length
from solver.topology.constants import MIN_ACCESS_WALL

WallAxis = Literal["x", "y"]


@dataclass(frozen=True)
class SharedWall:
    """恰好两房共边的内墙（法向可拖）。room_a 在左/上，room_b 在右/下。"""

    floor_id: str
    room_a: str
    room_b: str
    axis: WallAxis
    """共墙线坐标（竖墙为 x，横墙为 y）。"""
    coord: float
    """共边线段沿墙方向起止。"""
    along0: float
    along1: float

    @property
    def mid_along(self) -> float:
        return (self.along0 + self.along1) / 2

    @property
    def length(self) -> float:
        return self.along1 - self.along0


def list_shared_walls(
    placements: list,
    *,
    floor_id: str | None = None,
    min_length: float = MIN_ACCESS_WALL,
) -> list[SharedWall]:
    """
    枚举可编辑共墙：同层、非楼梯、共边≥min_length、无第三房压在同一共边线段（拒 T 接）。
    """
    rooms = [
        p
        for p in placements
        if not str(getattr(p, "room_id", "")).startswith("stair-")
        and (floor_id is None or getattr(p, "floor_id", None) == floor_id)
    ]
    walls: list[SharedWall] = []
    for i, a in enumerate(rooms):
        ra = _rect_of(a)
        if ra is None:
            continue
        for b in rooms[i + 1 :]:
            if getattr(a, "floor_id", None) != getattr(b, "floor_id", None):
                continue
            rb = _rect_of(b)
            if rb is None:
                continue
            wall = _shared_wall_between(
                str(a.room_id),
                ra,
                str(b.room_id),
                rb,
                floor_id=str(a.floor_id),
                min_length=min_length,
            )
            if wall is None:
                continue
            if _has_t_junction(wall, rooms, exclude={wall.room_a, wall.room_b}):
                continue
            walls.append(wall)
    return walls


def apply_wall_coord(
    rect_a: PlacementRect,
    rect_b: PlacementRect,
    *,
    axis: WallAxis,
    coord: float,
    hard_min: float = 0.9,
) -> tuple[PlacementRect | None, PlacementRect | None, str | None]:
    """
    左/上为 A、右/下为 B。返回 (new_a, new_b, error_code)。
    error_code: mutation.min_edge | mutation.wall_order
    """
    if axis == "x":
        # A 在左：A.right 与 B.left 共线
        a_left = rect_a.x
        b_right = rect_b.x + rect_b.width
        if coord <= a_left + hard_min - 1e-9 or coord >= b_right - hard_min + 1e-9:
            return None, None, "mutation.min_edge"
        if coord + 1e-9 < a_left or coord - 1e-9 > b_right:
            return None, None, "mutation.wall_order"
        new_a = PlacementRect(
            x=rect_a.x,
            y=rect_a.y,
            width=coord - rect_a.x,
            depth=rect_a.depth,
        )
        new_b = PlacementRect(
            x=coord,
            y=rect_b.y,
            width=b_right - coord,
            depth=rect_b.depth,
        )
    else:
        a_top = rect_a.y
        b_bottom = rect_b.y + rect_b.depth
        if coord <= a_top + hard_min - 1e-9 or coord >= b_bottom - hard_min + 1e-9:
            return None, None, "mutation.min_edge"
        if coord + 1e-9 < a_top or coord - 1e-9 > b_bottom:
            return None, None, "mutation.wall_order"
        new_a = PlacementRect(
            x=rect_a.x,
            y=rect_a.y,
            width=rect_a.width,
            depth=coord - rect_a.y,
        )
        new_b = PlacementRect(
            x=rect_b.x,
            y=coord,
            width=rect_b.width,
            depth=b_bottom - coord,
        )
    if (
        new_a.width < hard_min - 1e-9
        or new_a.depth < hard_min - 1e-9
        or new_b.width < hard_min - 1e-9
        or new_b.depth < hard_min - 1e-9
    ):
        return None, None, "mutation.min_edge"
    return new_a, new_b, None


def order_pair(
    id_a: str,
    rect_a: PlacementRect,
    id_b: str,
    rect_b: PlacementRect,
    axis: WallAxis,
) -> tuple[str, PlacementRect, str, PlacementRect]:
    """保证返回 (left/top, right/bottom)。"""
    if axis == "x":
        if rect_a.x <= rect_b.x:
            return id_a, rect_a, id_b, rect_b
        return id_b, rect_b, id_a, rect_a
    if rect_a.y <= rect_b.y:
        return id_a, rect_a, id_b, rect_b
    return id_b, rect_b, id_a, rect_a


def _rect_of(p: object) -> PlacementRect | None:
    try:
        r = p.rect  # type: ignore[attr-defined]
        if isinstance(r, PlacementRect):
            return r
        return PlacementRect(
            x=float(r.x),
            y=float(r.y),
            width=float(r.width),
            depth=float(r.depth),
        )
    except Exception:
        return None


def _shared_wall_between(
    id_a: str,
    ra: PlacementRect,
    id_b: str,
    rb: PlacementRect,
    *,
    floor_id: str,
    min_length: float,
) -> SharedWall | None:
    aa = from_placement(ra)
    bb = from_placement(rb)
    length = shared_edge_length(aa, bb)
    if length + 1e-9 < min_length:
        return None
    tol = 1e-6
    # 竖向共边（左右）→ axis=x
    for left, right, lid, rid, lrect, rrect in (
        (aa, bb, id_a, id_b, ra, rb),
        (bb, aa, id_b, id_a, rb, ra),
    ):
        if abs(left.right - right.left) <= tol:
            y0 = max(left.top, right.top)
            y1 = min(left.bottom, right.bottom)
            if y1 - y0 + 1e-9 >= min_length:
                # left 在左
                return SharedWall(
                    floor_id=floor_id,
                    room_a=lid,
                    room_b=rid,
                    axis="x",
                    coord=left.right,
                    along0=y0,
                    along1=y1,
                )
    # 水平共边（上下）→ axis=y
    for top, bottom, tid, bid, _trect, _brect in (
        (aa, bb, id_a, id_b, ra, rb),
        (bb, aa, id_b, id_a, rb, ra),
    ):
        if abs(top.bottom - bottom.top) <= tol:
            x0 = max(top.left, bottom.left)
            x1 = min(top.right, bottom.right)
            if x1 - x0 + 1e-9 >= min_length:
                return SharedWall(
                    floor_id=floor_id,
                    room_a=tid,
                    room_b=bid,
                    axis="y",
                    coord=top.bottom,
                    along0=x0,
                    along1=x1,
                )
    return None


def _has_t_junction(
    wall: SharedWall,
    rooms: list,
    *,
    exclude: set[str],
    tol: float = 1e-4,
) -> bool:
    """第三房若贴在同一共墙线上且沿墙投影与共边重叠 → T 接。"""
    for p in rooms:
        rid = str(getattr(p, "room_id", ""))
        if rid in exclude:
            continue
        if getattr(p, "floor_id", None) != wall.floor_id:
            continue
        r = _rect_of(p)
        if r is None:
            continue
        rr = from_placement(r)
        if wall.axis == "x":
            on_line = abs(rr.left - wall.coord) <= tol or abs(rr.right - wall.coord) <= tol
            if not on_line:
                continue
            y0 = max(rr.top, wall.along0)
            y1 = min(rr.bottom, wall.along1)
            if y1 - y0 > tol:
                return True
        else:
            on_line = abs(rr.top - wall.coord) <= tol or abs(rr.bottom - wall.coord) <= tol
            if not on_line:
                continue
            x0 = max(rr.left, wall.along0)
            x1 = min(rr.right, wall.along1)
            if x1 - x0 > tol:
                return True
    return False

"""不可变矩形几何 — solver 核心运算。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.schema.layout import PlacementRect


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    depth: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.depth

    @property
    def area(self) -> float:
        return self.width * self.depth

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.depth / 2)

    @property
    def aspect_ratio(self) -> float:
        short = min(self.width, self.depth)
        long = max(self.width, self.depth)
        return long / max(short, 1e-6)


def intersects(a: Rect, b: Rect) -> bool:
    return a.left < b.right and a.right > b.left and a.top < b.bottom and a.bottom > b.top


def intersection(a: Rect, b: Rect) -> Rect | None:
    if not intersects(a, b):
        return None
    x0 = max(a.left, b.left)
    y0 = max(a.top, b.top)
    x1 = min(a.right, b.right)
    y1 = min(a.bottom, b.bottom)
    w, d = x1 - x0, y1 - y0
    if w <= 0 or d <= 0:
        return None
    return Rect(x=x0, y=y0, width=w, depth=d)


def contains(outer: Rect, inner: Rect) -> bool:
    return (
        inner.left >= outer.left - 1e-9
        and inner.right <= outer.right + 1e-9
        and inner.top >= outer.top - 1e-9
        and inner.bottom <= outer.bottom + 1e-9
    )


def _axis_gap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    if a_max < b_min:
        return b_min - a_max
    if b_max < a_min:
        return a_min - b_max
    return 0.0


def distance_between(a: Rect, b: Rect) -> float:
    dx = _axis_gap(a.left, a.right, b.left, b.right)
    dy = _axis_gap(a.top, a.bottom, b.top, b.bottom)
    return (dx * dx + dy * dy) ** 0.5


def touches(a: Rect, b: Rect) -> bool:
    return shared_edge_length(a, b) > 0


def shared_edge_length(a: Rect, b: Rect, tolerance: float = 1e-6) -> float:
    """两矩形共享正交边的长度（米）。邻接判断的基础。"""
    length = 0.0

    # 垂直共享边（左右对齐）
    for x_edge in (a.left, a.right):
        if abs(x_edge - b.left) <= tolerance or abs(x_edge - b.right) <= tolerance:
            overlap = min(a.bottom, b.bottom) - max(a.top, b.top)
            if overlap > tolerance:
                length = max(length, overlap)

    # 水平共享边（上下对齐）
    for y_edge in (a.top, a.bottom):
        if abs(y_edge - b.top) <= tolerance or abs(y_edge - b.bottom) <= tolerance:
            overlap = min(a.right, b.right) - max(a.left, b.left)
            if overlap > tolerance:
                length = max(length, overlap)

    return length


def exterior_edges(
    room: Rect,
    buildable: Rect,
    *,
    tolerance: float = 0.05,
) -> dict[str, float]:
    """
    房间贴靠 buildable 外缘的各向边长（米）。

    坐标系：y=0 北，y 增大向南；x=0 西，x 增大向东。
    未贴靠方向不出现在字典中。
    """
    edges: dict[str, float] = {}
    if abs(room.top - buildable.top) <= tolerance:
        edges["north"] = room.width
    if abs(room.bottom - buildable.bottom) <= tolerance:
        edges["south"] = room.width
    if abs(room.left - buildable.left) <= tolerance:
        edges["west"] = room.depth
    if abs(room.right - buildable.right) <= tolerance:
        edges["east"] = room.depth
    return edges


def exterior_wall_length(
    room: Rect,
    buildable: Rect,
    *,
    tolerance: float = 0.05,
) -> float:
    """贴外墙总长度（米）。"""
    return sum(exterior_edges(room, buildable, tolerance=tolerance).values())


def from_placement(rect: PlacementRect) -> Rect:
    from packages.schema.layout import PlacementRect

    if not isinstance(rect, PlacementRect):
        raise TypeError("expected PlacementRect")
    return Rect(x=rect.x, y=rect.y, width=rect.width, depth=rect.depth)

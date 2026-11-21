"""建筑外围护边界 — 真实外墙线段（非「整面外墙」布尔）。

矩形可建与不规则多边形统一：返回连续 ``ExteriorWallSegment``，
供窗户 / 入口 / 朝向 / 暗卫共用。禁止三点采样把部分外墙当成整边。
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.schema.program import DesignProgram
from solver.geometry.buildable import program_uses_irregular_geometry
from solver.geometry.rect import Rect, exterior_edges, program_local_buildable

# 与 solver.evaluation.orientation.EDGE_TOLERANCE 对齐；此处不导入以免循环依赖
EDGE_TOLERANCE = 0.05


@dataclass(frozen=True)
class ExteriorWallSegment:
    """房间一侧上的一段真实外墙（model 坐标）。"""

    direction: str  # north/south/east/west
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return abs(self.x1 - self.x0) + abs(self.y1 - self.y0)

    @property
    def mid_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def mid_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def axis(self) -> str:
        """墙走向：水平墙为 x，竖向墙为 y。"""
        return "x" if self.direction in ("north", "south") else "y"

    def can_fit(self, opening_width: float, *, eps: float = 1e-9) -> bool:
        return self.length + eps >= opening_width


def program_exterior_segments(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> list[ExteriorWallSegment]:
    """房间贴靠真实可建外围护的全部连续线段。"""
    if not program_uses_irregular_geometry(program):
        return _rect_bbox_segments(room, program, tolerance=tolerance)
    return _polygon_segments(room, program, tolerance=tolerance)


def program_exterior_edges(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> dict[str, float]:
    """兼容旧 API：各向**真实线段长度之和**（非整边虚报）。"""
    out: dict[str, float] = {}
    for seg in program_exterior_segments(room, program, tolerance=tolerance):
        out[seg.direction] = out.get(seg.direction, 0.0) + seg.length
    return out


def pick_longest_exterior_segment(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
    min_length: float = 0.0,
) -> ExteriorWallSegment | None:
    """取最长且长度 ≥ ``min_length`` 的外墙段。"""
    segs = [
        s
        for s in program_exterior_segments(room, program, tolerance=tolerance)
        if s.length + 1e-9 >= min_length
    ]
    if not segs:
        return None
    return max(segs, key=lambda s: s.length)


def pick_longest_exterior_edge(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> tuple[str, float] | None:
    """兼容旧 API：返回 (direction, 该向线段总长)。"""
    edges = program_exterior_edges(room, program, tolerance=tolerance)
    if not edges:
        return None
    return max(edges.items(), key=lambda kv: kv[1])


def has_exterior_wall(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> bool:
    return bool(program_exterior_segments(room, program, tolerance=tolerance))


def _rect_bbox_segments(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float,
) -> list[ExteriorWallSegment]:
    buildable = program_local_buildable(program)
    edges = exterior_edges(room, buildable, tolerance=tolerance)
    segs: list[ExteriorWallSegment] = []
    if "north" in edges:
        segs.append(
            ExteriorWallSegment("north", room.left, room.top, room.right, room.top)
        )
    if "south" in edges:
        segs.append(
            ExteriorWallSegment(
                "south", room.left, room.bottom, room.right, room.bottom
            )
        )
    if "west" in edges:
        segs.append(
            ExteriorWallSegment("west", room.left, room.top, room.left, room.bottom)
        )
    if "east" in edges:
        segs.append(
            ExteriorWallSegment("east", room.right, room.top, room.right, room.bottom)
        )
    return segs


def _room_side_line(room: Rect, direction: str):
    from shapely.geometry import LineString

    if direction == "north":
        return LineString([(room.left, room.top), (room.right, room.top)])
    if direction == "south":
        return LineString([(room.left, room.bottom), (room.right, room.bottom)])
    if direction == "west":
        return LineString([(room.left, room.top), (room.left, room.bottom)])
    return LineString([(room.right, room.top), (room.right, room.bottom)])


def _polygon_segments(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float,
) -> list[ExteriorWallSegment]:
    from shapely.geometry import Point
    from solver.geometry.irregular import polygon_to_shapely

    poly = program.buildable_polygon
    if poly is None:
        return _rect_bbox_segments(room, program, tolerance=tolerance)

    geom = polygon_to_shapely(poly)
    boundary = geom.boundary
    probe = max(tolerance, 0.05)
    min_len = max(tolerance, 0.05)
    segs: list[ExteriorWallSegment] = []

    outward = {
        "north": (0.0, -probe),
        "south": (0.0, probe),
        "west": (-probe, 0.0),
        "east": (probe, 0.0),
    }

    for direction, (dx, dy) in outward.items():
        wall = _room_side_line(room, direction)
        hit = wall.intersection(boundary.buffer(tolerance))
        if hit.is_empty:
            continue
        for part in _iter_lines(hit):
            clipped = _clip_line_to_wall(part, wall)
            if clipped is None or clipped.length + 1e-9 < min_len:
                continue
            mx = (clipped.coords[0][0] + clipped.coords[-1][0]) / 2
            my = (clipped.coords[0][1] + clipped.coords[-1][1]) / 2
            # 外探点须在可建体外，排除内部分割
            if geom.contains(Point(mx + dx, my + dy)):
                continue
            x0, y0 = clipped.coords[0]
            x1, y1 = clipped.coords[-1]
            segs.append(
                ExteriorWallSegment(
                    direction, float(x0), float(y0), float(x1), float(y1)
                )
            )
    return _merge_colinear(segs)


def _iter_lines(geom):
    from shapely.geometry import GeometryCollection, LineString, MultiLineString

    if geom.is_empty:
        return
    if isinstance(geom, LineString):
        if geom.length > 0:
            yield geom
        return
    if isinstance(geom, MultiLineString | GeometryCollection):
        for g in geom.geoms:
            yield from _iter_lines(g)


def _clip_line_to_wall(part, wall):
    from shapely.geometry import LineString, Point

    coords = list(part.coords)
    if len(coords) < 2:
        return None
    params = [wall.project(Point(x, y)) for x, y in coords]
    lo, hi = min(params), max(params)
    if hi - lo <= 1e-9:
        return None
    p0 = wall.interpolate(lo)
    p1 = wall.interpolate(hi)
    return LineString([(p0.x, p0.y), (p1.x, p1.y)])


def _merge_colinear(segs: list[ExteriorWallSegment]) -> list[ExteriorWallSegment]:
    if not segs:
        return []
    by_dir: dict[str, list[ExteriorWallSegment]] = {}
    for s in segs:
        by_dir.setdefault(s.direction, []).append(s)

    merged: list[ExteriorWallSegment] = []
    for direction, group in by_dir.items():
        horizontal = direction in ("north", "south")
        items = sorted(
            group,
            key=lambda s: (
                min(s.x0, s.x1) if horizontal else min(s.y0, s.y1),
                max(s.x0, s.x1) if horizontal else max(s.y0, s.y1),
            ),
        )
        cur = items[0]
        for nxt in items[1:]:
            if horizontal and abs(cur.y0 - nxt.y0) <= 1e-6:
                a0, a1 = sorted((cur.x0, cur.x1))
                b0, b1 = sorted((nxt.x0, nxt.x1))
                if b0 <= a1 + 1e-6:
                    y = cur.y0
                    cur = ExteriorWallSegment(
                        direction, min(a0, b0), y, max(a1, b1), y
                    )
                    continue
            elif (not horizontal) and abs(cur.x0 - nxt.x0) <= 1e-6:
                a0, a1 = sorted((cur.y0, cur.y1))
                b0, b1 = sorted((nxt.y0, nxt.y1))
                if b0 <= a1 + 1e-6:
                    x = cur.x0
                    cur = ExteriorWallSegment(
                        direction, x, min(a0, b0), x, max(a1, b1)
                    )
                    continue
            merged.append(cur)
            cur = nxt
        merged.append(cur)
    return merged

"""建筑外围护边界 — 矩形可建区与不规则多边形统一查询。

供窗户、暗卫 Gate、朝向、入口共用；禁止各模块自行只用外接矩形 bbox。
"""

from __future__ import annotations

from packages.schema.program import DesignProgram
from solver.evaluation.orientation import EDGE_TOLERANCE
from solver.geometry.buildable import program_uses_irregular_geometry
from solver.geometry.rect import Rect, exterior_edges, program_local_buildable


def program_exterior_edges(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> dict[str, float]:
    """
    房间贴靠**真实可建外围护**的各向边长（米）。

    - 矩形可建：等价于 ``exterior_edges(room, bbox)``
    - 不规则（L / 庭院）：外向偏移点落在可建多边形外 → 该侧为外墙
      （含凹角与内院侧墙，不会被 bbox 误判）
    """
    if not program_uses_irregular_geometry(program):
        return exterior_edges(
            room, program_local_buildable(program), tolerance=tolerance
        )
    return _polygon_exterior_edges(room, program, tolerance=tolerance)


def pick_longest_exterior_edge(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> tuple[str, float] | None:
    """取最长外墙段；无外墙返回 None。"""
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
    return bool(program_exterior_edges(room, program, tolerance=tolerance))


def _polygon_exterior_edges(
    room: Rect,
    program: DesignProgram,
    *,
    tolerance: float,
) -> dict[str, float]:
    from shapely.geometry import Point

    from solver.geometry.irregular import polygon_to_shapely

    poly = program.buildable_polygon
    if poly is None:
        return exterior_edges(
            room, program_local_buildable(program), tolerance=tolerance
        )

    geom = polygon_to_shapely(poly)
    # 稍放大容差，避免边界数值抖动把外墙判成「内」
    probe = max(tolerance, 0.05)
    edges: dict[str, float] = {}

    samples: dict[str, list[tuple[float, float]]] = {
        "north": [
            (room.left + room.width * t, room.top - probe)
            for t in (0.25, 0.5, 0.75)
        ],
        "south": [
            (room.left + room.width * t, room.bottom + probe)
            for t in (0.25, 0.5, 0.75)
        ],
        "west": [
            (room.left - probe, room.top + room.depth * t)
            for t in (0.25, 0.5, 0.75)
        ],
        "east": [
            (room.right + probe, room.top + room.depth * t)
            for t in (0.25, 0.5, 0.75)
        ],
    }
    lengths = {
        "north": room.width,
        "south": room.width,
        "west": room.depth,
        "east": room.depth,
    }

    for name, pts in samples.items():
        # 外墙：多数外探点不在可建体内（含洞/凹角）
        outside = 0
        for x, y in pts:
            if not geom.contains(Point(x, y)):
                outside += 1
        if outside >= 2:
            # 还要求墙身本身贴在可建边界附近（避免「整房悬空」误报）
            if _edge_near_boundary(room, name, geom, tolerance=tolerance):
                edges[name] = lengths[name]
    return edges


def _edge_near_boundary(
    room: Rect,
    edge: str,
    geom,
    *,
    tolerance: float,
) -> bool:
    """墙线上采样点应落在多边形边界附近（覆盖或贴边）。"""
    from shapely.geometry import Point

    if edge == "north":
        pts = [(room.left + room.width * t, room.top) for t in (0.25, 0.5, 0.75)]
    elif edge == "south":
        pts = [(room.left + room.width * t, room.bottom) for t in (0.25, 0.5, 0.75)]
    elif edge == "west":
        pts = [(room.left, room.top + room.depth * t) for t in (0.25, 0.5, 0.75)]
    else:
        pts = [(room.right, room.top + room.depth * t) for t in (0.25, 0.5, 0.75)]

    hit = 0
    for x, y in pts:
        p = Point(x, y)
        if geom.covers(p) or geom.boundary.distance(p) <= tolerance + 1e-6:
            hit += 1
    return hit >= 2

"""可建几何解析 — Phase 8.4.1 irregular site pipeline 接入点。"""

from __future__ import annotations

from dataclasses import dataclass

from packages.schema.program import DesignProgram
from packages.schema.site import Polygon2D, Rect2D, SiteSpec
from solver.geometry.irregular import (
    inset_with_setbacks,
    prepare_buildable_rects,
)
from solver.geometry.rect import Rect, program_local_buildable


@dataclass(frozen=True)
class BuildableGeometry:
    """normalize 后 solver 消费的可建几何。"""

    buildable: Rect2D
    free_rects: list[Rect]
    polygon: Polygon2D | None
    uses_irregular: bool


def site_has_irregular_input(site: SiteSpec) -> bool:
    return site.buildable_polygon is not None or site.site_polygon is not None


def _bbox_of_rects(rects: list[Rect]) -> Rect2D:
    if not rects:
        raise ValueError("free rects 为空，无法推导 bounding box")
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.right for r in rects)
    y1 = max(r.bottom for r in rects)
    return Rect2D(x=x0, y=y0, width=x1 - x0, depth=y1 - y0)


def _translate_polygon(poly: Polygon2D, dx: float, dy: float) -> Polygon2D:
    from packages.schema.site import Point2D

    return Polygon2D(
        exterior=[Point2D(x=p.x - dx, y=p.y - dy) for p in poly.exterior],
        holes=[
            [Point2D(x=p.x - dx, y=p.y - dy) for p in ring]
            for ring in poly.holes
        ],
    )


def _normalize_to_local_frame(
    free: list[Rect],
    polygon: Polygon2D | None,
) -> tuple[Rect2D, list[Rect], Polygon2D | None]:
    """对齐 solver 局部坐标系：origin = union bbox 西北角。"""
    bbox = _bbox_of_rects(free)
    ox, oy = bbox.x, bbox.y
    free_local = [
        Rect(x=r.x - ox, y=r.y - oy, width=r.width, depth=r.depth) for r in free
    ]
    buildable = Rect2D(x=0.0, y=0.0, width=bbox.width, depth=bbox.depth)
    poly_local = (
        _translate_polygon(polygon, ox, oy) if polygon is not None else None
    )
    return buildable, free_local, poly_local


def _rect2d_list(rects: list[Rect]) -> list[Rect2D]:
    return [
        Rect2D(x=r.x, y=r.y, width=r.width, depth=r.depth)
        for r in rects
    ]


def resolve_buildable_geometry(site: SiteSpec) -> BuildableGeometry:
    """
    矩形默认路径与 irregular 路径统一入口。

    - 无 polygon → 单一 buildable_envelope
    - 有 polygon → prepare_buildable_rects + union bbox
    """
    envelope = site.buildable_envelope
    if envelope is None:
        raise ValueError("SiteSpec must derive buildable_envelope")

    if not site_has_irregular_input(site):
        local = Rect2D(x=0.0, y=0.0, width=envelope.width, depth=envelope.depth)
        return BuildableGeometry(
            buildable=local,
            free_rects=[Rect(x=0.0, y=0.0, width=envelope.width, depth=envelope.depth)],
            polygon=None,
            uses_irregular=False,
        )

    poly = site.buildable_polygon
    if poly is None and site.site_polygon is not None:
        poly = inset_with_setbacks(site.site_polygon, site.setbacks)

    free = prepare_buildable_rects(
        site_polygon=site.site_polygon,
        buildable_polygon=site.buildable_polygon,
        setbacks=site.setbacks,
        fallback_rect=envelope,
    )
    if not free:
        raise ValueError("不规则可建区域分解为空")

    buildable, free_local, poly_local = _normalize_to_local_frame(free, poly)
    return BuildableGeometry(
        buildable=buildable,
        free_rects=free_local,
        polygon=poly_local,
        uses_irregular=True,
    )


def apply_buildable_geometry(program: DesignProgram) -> None:
    """写入 DesignProgram 的可建字段（normalize 后调用）。"""
    geom = resolve_buildable_geometry(program.site)
    program.buildable = geom.buildable
    program.buildable_free_rects = _rect2d_list(geom.free_rects)
    program.buildable_polygon = geom.polygon


def program_pack_rects(program: DesignProgram) -> list[Rect]:
    """Packing / coverage 使用的 free rect 列表。"""
    if program.buildable_free_rects:
        return [
            Rect(x=r.x, y=r.y, width=r.width, depth=r.depth)
            for r in program.buildable_free_rects
        ]
    return [program_local_buildable(program)]


def program_footprint_area(program: DesignProgram) -> float:
    """可建 union 面积（非 bbox 面积）。"""
    return sum(r.area for r in program_pack_rects(program))


def program_uses_irregular_geometry(program: DesignProgram) -> bool:
    return program.buildable_polygon is not None and bool(program.buildable_free_rects)


def rect_inside_buildable(rect: Rect, program: DesignProgram) -> bool:
    """placement 是否完全落在可建 union 内。"""
    from solver.geometry.irregular import contains_axis_aligned_rect
    from solver.geometry.rect import contains

    if program.buildable_polygon is not None:
        return contains_axis_aligned_rect(
            program.buildable_polygon,
            x=rect.x,
            y=rect.y,
            width=rect.width,
            depth=rect.depth,
        )
    return contains(program_local_buildable(program), rect)

"""Phase 8.4 — irregular site geometry (Shapely opt-in)。"""

from __future__ import annotations

import pytest

pytest.importorskip("shapely")

from packages.schema.site import Point2D, Polygon2D, Rect2D, SetbackSpec
from solver.geometry.irregular import (
    IrregularGeometryError,
    contains_axis_aligned_rect,
    inset_with_setbacks,
    is_orthogonal_polygon,
    orthogonal_free_rects,
    prepare_buildable_rects,
    rect_to_polygon,
    uniform_inset,
)


def _l_shape() -> Polygon2D:
    # 10x10 square minus NE 5x5 → L
    return Polygon2D(
        exterior=[
            Point2D(x=0, y=0),
            Point2D(x=10, y=0),
            Point2D(x=10, y=5),
            Point2D(x=5, y=5),
            Point2D(x=5, y=10),
            Point2D(x=0, y=10),
        ]
    )


def _courtyard() -> Polygon2D:
    return Polygon2D(
        exterior=[
            Point2D(x=0, y=0),
            Point2D(x=12, y=0),
            Point2D(x=12, y=12),
            Point2D(x=0, y=12),
        ],
        holes=[
            [
                Point2D(x=4, y=4),
                Point2D(x=8, y=4),
                Point2D(x=8, y=8),
                Point2D(x=4, y=8),
            ]
        ],
    )


def test_l_shape_is_orthogonal():
    assert is_orthogonal_polygon(_l_shape())


def test_diagonal_not_orthogonal():
    poly = Polygon2D(
        exterior=[
            Point2D(x=0, y=0),
            Point2D(x=4, y=0),
            Point2D(x=3, y=3),
        ]
    )
    assert not is_orthogonal_polygon(poly)


def test_orthogonal_free_rects_cover_l_shape():
    rects = orthogonal_free_rects(_l_shape())
    assert len(rects) >= 2
    area = sum(r.area for r in rects)
    assert abs(area - 75.0) < 1e-6  # 100 - 25


def test_courtyard_free_rects():
    rects = orthogonal_free_rects(_courtyard())
    assert rects
    area = sum(r.area for r in rects)
    assert abs(area - (144 - 16)) < 1e-6


def test_contains_rect():
    poly = rect_to_polygon(Rect2D(x=0, y=0, width=10, depth=10))
    assert contains_axis_aligned_rect(poly, x=1, y=1, width=2, depth=2)
    assert not contains_axis_aligned_rect(poly, x=9, y=9, width=3, depth=3)


def test_uniform_inset():
    poly = rect_to_polygon(Rect2D(x=0, y=0, width=10, depth=10))
    inset = uniform_inset(poly, 1.0)
    rects = orthogonal_free_rects(inset)
    assert len(rects) == 1
    assert abs(rects[0].width - 8.0) < 1e-6
    assert abs(rects[0].depth - 8.0) < 1e-6


def test_inset_with_setbacks_uses_max_edge():
    poly = rect_to_polygon(Rect2D(x=0, y=0, width=20, depth=20))
    out = inset_with_setbacks(poly, SetbackSpec(north=2, south=1, east=1, west=1))
    rects = orthogonal_free_rects(out)
    assert abs(rects[0].width - 16.0) < 1e-6  # max=2


def test_non_orthogonal_free_rects_rejected():
    poly = Polygon2D(
        exterior=[
            Point2D(x=0, y=0),
            Point2D(x=4, y=0),
            Point2D(x=3, y=3),
        ]
    )
    with pytest.raises(IrregularGeometryError):
        orthogonal_free_rects(poly)


def test_prepare_buildable_rects_fallback():
    rects = prepare_buildable_rects(
        fallback_rect=Rect2D(x=1, y=2, width=8, depth=6)
    )
    assert len(rects) == 1
    assert rects[0].x == 1 and rects[0].y == 2


def test_site_spec_accepts_polygon_fields():
    from packages.schema.site import SiteSpec

    site = SiteSpec(
        width=12,
        depth=12,
        site_polygon=_l_shape(),
    )
    assert site.site_polygon is not None
    assert site.buildable_envelope is not None  # 矩形路径仍推导

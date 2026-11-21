"""真实外围护边界 — L 形 / 庭院不得被 bbox 误判。"""

from __future__ import annotations

import pytest

pytest.importorskip("shapely")

from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import Point2D, Polygon2D, SiteSpec
from solver.evaluation.architectural_gate import evaluate_architectural_gate
from solver.geometry.buildable import apply_buildable_geometry
from solver.geometry.exterior import has_exterior_wall, program_exterior_edges
from solver.geometry.rect import Rect
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)


def _l_poly() -> Polygon2D:
    # 缺右上角：bbox 10×10，真实面积 75
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


def _courtyard_poly() -> Polygon2D:
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


def _program_with_poly(poly: Polygon2D, *, w: float = 10, d: float = 10) -> DesignProgram:
    rooms = [
        RoomSpec(
            id="bath",
            name="卫生间",
            category=RoomCategory.WET,
            target_area=4,
            floor_id="F1",
        ),
    ]
    program = DesignProgram(
        project_id="ext-wall",
        site=SiteSpec(width=w, depth=d, buildable_polygon=poly),
        buildable=SiteSpec(width=w, depth=d).buildable_envelope,
        floors=[FloorSpec(id="F1", label="一层", room_ids=["bath"])],
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(),
    )
    apply_buildable_geometry(program)
    return program


def test_l_shape_reentrant_edge_is_exterior():
    """贴 L 形凹角墙（bbox 内部）仍算外墙。"""
    program = _program_with_poly(_l_poly())
    # 房间贴在缺口北侧墙：底边 y=5、x=5..9 — 对 bbox 不是南缘，但是多边形外墙
    room = Rect(x=5, y=2, width=4, depth=3)  # bottom=5 along reentrant
    edges = program_exterior_edges(room, program)
    assert "south" in edges
    assert has_exterior_wall(room, program)


def test_l_shape_fully_interior_not_exterior():
    program = _program_with_poly(_l_poly())
    room = Rect(x=1, y=1, width=3, depth=3)
    assert program_exterior_edges(room, program) == {}


def test_courtyard_inner_wall_is_exterior():
    """贴内院侧墙算外墙（采光/暗卫应对齐）。"""
    program = _program_with_poly(_courtyard_poly(), w=12, d=12)
    # 贴洞的西侧：房间右缘 x=4
    room = Rect(x=1, y=4.5, width=3, depth=3)  # right=4
    edges = program_exterior_edges(room, program)
    assert "east" in edges


def test_black_wet_gate_uses_polygon_exterior():
    """凹角外墙卫生间不应被 Gate 判黑卫。"""
    program = _program_with_poly(_l_poly())
    bath = RoomPlacement(
        room_id="bath",
        floor_id="F1",
        rect=PlacementRect(x=5, y=2, width=4, depth=3),
        source=PlacementSource.PROGRAM,
        name="卫生间",
        category="wet",
    )
    cand = LayoutCandidate(
        id="bw",
        seed=0,
        floors=[FloorLayout(floor_id="F1", placements=[bath])],
        realized_connections=[],
    )
    gate = evaluate_architectural_gate(program, cand)
    assert not any(i.code == "black_wet" for i in gate.all_issues)

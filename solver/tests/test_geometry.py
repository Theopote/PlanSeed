"""几何运算单元测试。"""

import pytest
from solver.geometry.rect import (
    Rect,
    contains,
    distance_between,
    exterior_edges,
    exterior_wall_length,
    intersection,
    intersects,
    shared_edge_length,
    touches,
)
from solver.geometry.snap import snap_rect, snap_value


class TestSnap:
    def test_snap_value(self):
        assert snap_value(0.29) == pytest.approx(0.3)
        assert snap_value(0.31) == pytest.approx(0.3)
        assert snap_value(0.44) == pytest.approx(0.3)
        assert snap_value(0.46) == pytest.approx(0.6)

    def test_snap_rect(self):
        r = snap_rect(Rect(x=0.29, y=0.31, width=3.21, depth=2.19))
        assert r.x == pytest.approx(0.3)
        assert r.y == pytest.approx(0.3)


class TestRect:
    def test_properties(self):
        r = Rect(x=1, y=2, width=4, depth=3)
        assert r.left == 1
        assert r.right == 5
        assert r.top == 2
        assert r.bottom == 5
        assert r.area == 12
        assert r.center == (3, 3.5)

    def test_intersects_and_intersection(self):
        a = Rect(x=0, y=0, width=2, depth=2)
        b = Rect(x=1, y=1, width=2, depth=2)
        assert intersects(a, b)
        inter = intersection(a, b)
        assert inter is not None
        assert inter.area == pytest.approx(1.0)

    def test_no_overlap(self):
        a = Rect(x=0, y=0, width=1, depth=1)
        b = Rect(x=2, y=0, width=1, depth=1)
        assert not intersects(a, b)
        assert intersection(a, b) is None

    def test_contains(self):
        outer = Rect(x=0, y=0, width=10, depth=10)
        inner = Rect(x=1, y=1, width=2, depth=2)
        assert contains(outer, inner)

    def test_shared_edge_length_adjacent(self):
        a = Rect(x=0, y=0, width=3, depth=4)
        b = Rect(x=3, y=0, width=2, depth=4)
        assert shared_edge_length(a, b) == pytest.approx(4.0)
        assert touches(a, b)

    def test_shared_edge_length_insufficient(self):
        a = Rect(x=0, y=0, width=3, depth=1)
        b = Rect(x=3, y=0, width=2, depth=1)
        assert shared_edge_length(a, b) == pytest.approx(1.0)

    def test_distance_between_separated(self):
        a = Rect(x=0, y=0, width=1, depth=1)
        b = Rect(x=3, y=0, width=1, depth=1)
        assert distance_between(a, b) == pytest.approx(2.0)

    def test_exterior_edges_and_wall_length(self):
        buildable = Rect(x=0, y=0, width=10, depth=12)
        sw = Rect(x=0, y=10, width=4, depth=2)  # 贴南+西
        edges = exterior_edges(sw, buildable)
        assert edges["south"] == pytest.approx(4.0)
        assert edges["west"] == pytest.approx(2.0)
        assert "north" not in edges
        assert exterior_wall_length(sw, buildable) == pytest.approx(6.0)

    def test_interior_room_has_no_exterior(self):
        buildable = Rect(x=0, y=0, width=10, depth=10)
        inner = Rect(x=2, y=2, width=3, depth=3)
        assert exterior_edges(inner, buildable) == {}
        assert exterior_wall_length(inner, buildable) == 0.0

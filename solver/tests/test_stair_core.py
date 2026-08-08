"""StairCore / free-rects 测试。"""

from __future__ import annotations

import random

import pytest

from packages.schema.core import CorePlacement
from packages.schema.layout import PlacementSource
from solver.circulation.stair_core import choose_core_placement, place_stair_core, resolve_stair_core_spec
from solver.geometry.free_rects import subtract_rect
from solver.geometry.rect import Rect
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program


class TestFreeRects:
    def test_subtract_center_hole_gives_up_to_four(self):
        outer = Rect(x=0, y=0, width=11, depth=13)
        hole = Rect(x=4, y=4, width=1.8, depth=4.2)
        parts = subtract_rect(outer, hole)
        assert 3 <= len(parts) <= 4
        assert abs(sum(p.area for p in parts) + hole.area - outer.area) < 0.01


class TestStairCore:
    def test_default_size_not_full_depth(self):
        spec = resolve_stair_core_spec(stair_width=1.8, stair_depth=4.2)
        core = place_stair_core(
            floor_width=11, floor_depth=13, spec=spec, placement=CorePlacement.WEST
        )
        assert core.rect.width == pytest.approx(1.8)
        assert core.rect.depth == pytest.approx(4.2)
        assert core.rect.area == pytest.approx(1.8 * 4.2)
        # 不再是 1.6×13
        assert core.rect.area < 20

    def test_seed_can_vary_placement(self):
        placements = set()
        for seed in range(40):
            rng = random.Random(seed)
            placements.add(choose_core_placement(rng))
        assert len(placements) >= 3

    def test_guillotine_stair_is_core_not_strip(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        stairs = [
            p
            for fl in candidate.floors
            for p in fl.placements
            if p.source == PlacementSource.GENERATED and p.room_id.startswith("stair")
        ]
        assert len(stairs) == 2
        for s in stairs:
            assert s.rect.area == pytest.approx(1.8 * 4.2, abs=0.5)
            assert s.rect.depth < 13.0 - 1e-6 or s.rect.width < 11.0 - 1e-6

    def test_stair_core_aligned_across_floors(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=7)
        f1, f2 = candidate.floors
        assert f1.stair_x0 == pytest.approx(f2.stair_x0, abs=0.01)
        assert f1.stair_y0 == pytest.approx(f2.stair_y0, abs=0.01)
        assert f1.stair_x1 == pytest.approx(f2.stair_x1, abs=0.01)
        assert f1.stair_y1 == pytest.approx(f2.stair_y1, abs=0.01)
        assert f1.core_placement == f2.core_placement

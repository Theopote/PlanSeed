"""StairCore / free-rects 测试。"""

from __future__ import annotations

import random

import pytest

from packages.schema.core import CorePlacement, StairCoreSpec
from packages.schema.layout import PlacementSource
from solver.circulation.stair_core import (
    CorePlacementFailure,
    choose_core_placement,
    place_stair_core,
    place_stair_core_resolving,
    resolve_stair_core_spec,
)
from solver.constraints.checker_impl import DefaultConstraintChecker
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

    def test_subtract_multiple_holes(self):
        from solver.geometry.free_rects import subtract_rects

        outer = Rect(x=0, y=0, width=10, depth=8)
        holes = [
            Rect(x=3, y=0, width=2, depth=4),
            Rect(x=7, y=5, width=2, depth=2),
        ]
        parts = subtract_rects([outer], holes)
        assert parts
        assert abs(sum(p.area for p in parts) + sum(h.area for h in holes) - outer.area) < 0.05


class TestStairCore:
    def test_default_size_not_full_depth(self):
        spec = resolve_stair_core_spec(stair_width=1.8, stair_depth=4.2)
        core = place_stair_core(
            floor_width=11, floor_depth=13, spec=spec, placement=CorePlacement.WEST
        )
        assert core.rect.width == pytest.approx(1.8)
        assert core.rect.depth == pytest.approx(4.2)
        assert core.rect.area == pytest.approx(1.8 * 4.2)
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

    def test_does_not_shrink_when_too_large(self):
        """放不下时抛 CorePlacementFailure，绝不缩小。"""
        spec = StairCoreSpec(width=1.8, depth=4.2)
        with pytest.raises(CorePlacementFailure):
            place_stair_core(
                floor_width=3.0,
                floor_depth=3.0,
                spec=spec,
                placement=CorePlacement.WEST,
            )

    def test_resolving_tries_alt_orientation_before_fail(self):
        """窄长 footprint：默认 ns 放不下，ew 可放入。"""
        spec = StairCoreSpec(width=1.8, depth=4.2)
        # 3×5：ns 要 1.8×4.2 OK；用更极端的 5×2 使 ns(1.8×4.2) 失败、ew(4.2×1.8) 成功
        core = place_stair_core_resolving(
            floor_width=5.0,
            floor_depth=2.0,
            spec=spec,
            primary_placement=CorePlacement.WEST,  # 默认 ns
            rng=random.Random(0),
        )
        assert core.orientation == "ew"
        assert core.rect.width == pytest.approx(4.2)
        assert core.rect.depth == pytest.approx(1.8)

    def test_resolving_fails_when_impossible(self):
        spec = StairCoreSpec(width=1.8, depth=4.2)
        with pytest.raises(CorePlacementFailure):
            place_stair_core_resolving(
                floor_width=2.0,
                floor_depth=2.0,
                spec=spec,
                primary_placement=CorePlacement.CENTER,
                rng=random.Random(1),
            )

    def test_guillotine_marks_core_unfit_invalid(self):
        program = benchmark_program()
        program.site.stair_width = 1.8
        program.site.stair_depth = 4.2
        # 缩小 buildable 使楼梯无法放入
        program.buildable.width = 2.0
        program.buildable.depth = 2.0
        program.site.width = 2.0
        program.site.depth = 2.0

        candidate = GuillotineGenerator().generate(program, seed=0)
        assert candidate.metrics.get("core_unfit") is True
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "geometry.core_unfit" for v in validation.hard_violations)
        # 尺寸未被缩小塞进方案
        stairs = [
            p
            for fl in candidate.floors
            for p in fl.placements
            if p.source == PlacementSource.GENERATED
        ]
        assert stairs == []

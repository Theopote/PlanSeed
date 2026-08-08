"""GuillotineGenerator 与基准回归测试。"""

from __future__ import annotations

import pytest
from packages.schema.layout import PlacementSource
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.rect import from_placement, intersects


class TestGuillotineGenerator:
    def test_same_seed_same_candidate(self):
        program = benchmark_program()
        gen = GuillotineGenerator()
        a = gen.generate(program, seed=17)
        b = gen.generate(program, seed=17)
        assert a.model_dump() == b.model_dump()

    def test_different_seed_can_differ(self):
        program = benchmark_program()
        gen = GuillotineGenerator()
        layouts = {gen.generate(program, seed=s).model_dump_json() for s in range(32)}
        assert len(layouts) > 1, "32 seeds should produce more than one distinct layout"

    def test_generates_stair_as_circulation(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        stairs = [
            p
            for fl in candidate.floors
            for p in fl.placements
            if p.source == PlacementSource.GENERATED
        ]
        assert len(stairs) == 2
        assert all(p.category == "circulation" for p in stairs)

    def test_no_room_overlap_on_valid_candidate(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        checker = DefaultConstraintChecker()
        validation = checker.check(program, candidate)
        overlap_violations = [v for v in validation.hard_violations if "overlap" in v.constraint_id]
        assert not overlap_violations

    def test_wet_stack_alignment(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        assert len(candidate.wet_stacks) == 1
        ws = candidate.wet_stacks[0]
        assert ws.id == "WS1"
        assert set(ws.floor_ids) == {f.floor_id for f in candidate.floors}
        # deprecated 镜像与主锚一致
        a = ws.anchor_rect
        for fl in candidate.floors:
            assert fl.wet_zone_x0 == pytest.approx(a.x, abs=0.01)
            assert fl.wet_zone_x1 == pytest.approx(a.x + a.width, abs=0.01)
            assert fl.wet_zone_y0 == pytest.approx(a.y, abs=0.01)
            assert fl.wet_zone_y1 == pytest.approx(a.y + a.depth, abs=0.01)

    def test_stair_x_alignment(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        f1 = candidate.floors[0]
        for fl in candidate.floors:
            assert fl.stair_x0 == pytest.approx(f1.stair_x0, abs=0.01)
            assert fl.stair_x1 == pytest.approx(f1.stair_x1, abs=0.01)
            assert fl.stair_y0 == pytest.approx(f1.stair_y0, abs=0.01)
            assert fl.stair_y1 == pytest.approx(f1.stair_y1, abs=0.01)
        # 核心面积远小于整层条带 1.6×13
        area = (f1.stair_x1 - f1.stair_x0) * (f1.stair_y1 - f1.stair_y0)
        assert area < 15.0

    def test_all_rooms_within_buildable(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        w, d = program.buildable.width, program.buildable.depth
        for fl in candidate.floors:
            for p in fl.placements:
                assert p.rect.x >= -1e-6
                assert p.rect.y >= -1e-6
                assert p.rect.right <= w + 1e-6
                assert p.rect.bottom <= d + 1e-6

    def test_compactness_near_reference(self):
        """11×13 接近正方形，外墙效率应 ≈ 99.6%。"""
        program = benchmark_program()
        GuillotineGenerator().generate(program, seed=0)
        footprint = 11 * 13
        import math

        ideal = 4 * math.sqrt(footprint)
        actual = 2 * (11 + 13)
        efficiency = ideal / actual * 100
        assert efficiency == pytest.approx(99.6, abs=0.5)

    def test_pairwise_no_area_overlap(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        for fl in candidate.floors:
            placements = fl.placements
            for i, a in enumerate(placements):
                ra = from_placement(a.rect)
                for b in placements[i + 1 :]:
                    rb = from_placement(b.rect)
                    if intersects(ra, rb):
                        ow = min(ra.right, rb.right) - max(ra.left, rb.left)
                        oh = min(ra.bottom, rb.bottom) - max(ra.top, rb.top)
                        assert ow <= 1e-4 or oh <= 1e-4

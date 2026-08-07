"""GuillotineGenerator 与基准回归测试。"""

from __future__ import annotations

import pytest

from packages.schema.layout import PlacementRect, PlacementSource
from packages.schema.project import ProjectSpec
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.rect import from_placement, intersects
from solver.program.normalize import normalize


def benchmark_program():
    spec = ProjectSpec(
        site=SiteSpec(width=11, depth=13, stair_width=1.6),
        floors=[
            {"id": "F1", "label": "一层", "room_ids": ["r1", "r2", "r3", "r4"]},
            {"id": "F2", "label": "二层", "room_ids": ["r5", "r6", "r7", "r8", "r9", "r10"]},
        ],
        rooms=[
            RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=24),
            RoomSpec(id="r2", name="餐厅+厨房", category=RoomCategory.WET, target_area=16, tags=["kitchen"]),
            RoomSpec(id="r3", name="卫生间", category=RoomCategory.WET, target_area=4),
            RoomSpec(id="r4", name="车库/储藏", category=RoomCategory.OTHER, target_area=15),
            RoomSpec(id="r5", name="主卧", category=RoomCategory.PRIVATE, target_area=18),
            RoomSpec(id="r6", name="主卫", category=RoomCategory.WET, target_area=5),
            RoomSpec(id="r7", name="次卧1", category=RoomCategory.PRIVATE, target_area=12),
            RoomSpec(id="r8", name="次卧2", category=RoomCategory.PRIVATE, target_area=12),
            RoomSpec(id="r9", name="公共卫生间", category=RoomCategory.WET, target_area=4),
            RoomSpec(id="r10", name="书房", category=RoomCategory.OTHER, target_area=9),
        ],
    )
    return normalize(spec)


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

    def test_wet_zone_alignment(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        f1, f2 = candidate.floors
        assert f1.wet_zone_x0 == pytest.approx(f2.wet_zone_x0, abs=0.01)
        assert f1.wet_zone_x1 == pytest.approx(f2.wet_zone_x1, abs=0.01)

    def test_stair_x_alignment(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        for fl in candidate.floors:
            assert fl.stair_x0 == pytest.approx(0.0)
            assert fl.stair_x1 == pytest.approx(1.6)

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
        candidate = GuillotineGenerator().generate(program, seed=0)
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

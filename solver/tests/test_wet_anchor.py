"""ADR-010 Step B — 湿区锚点放置单元测试。"""

from __future__ import annotations

import pytest
from solver.evaluation.vertical import rect_iou
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.generators.wet_anchor import anchor_floor_id, place_room_at_wet_anchor
from solver.geometry.rect import Rect, from_placement


class TestWetAnchorHelpers:
    def test_anchor_floor_is_wet_heaviest(self) -> None:
        program = benchmark_program()
        assert anchor_floor_id(program) == "F1"

    def test_place_room_prefers_exact_anchor_footprint(self) -> None:
        anchor = Rect(x=2.0, y=3.0, width=4.0, depth=3.0)
        pack = Rect(x=0.0, y=0.0, width=11.0, depth=13.0)
        placed = place_room_at_wet_anchor(
            pack,
            anchor,
            min_area=10.0,
            max_area=14.0,
        )
        assert placed is not None
        assert from_placement(placed).x == pytest.approx(2.0)
        assert from_placement(placed).y == pytest.approx(3.0)


class TestWetAnchorGenerator:
    def test_benchmark_bathroom_pair_aligned(self) -> None:
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        f1r3 = next(p for p in candidate.floors[0].placements if p.room_id == "r3")
        f2r9 = next(p for p in candidate.floors[1].placements if p.room_id == "r9")
        assert rect_iou(from_placement(f1r3.rect), from_placement(f2r9.rect)) == pytest.approx(
            1.0
        )

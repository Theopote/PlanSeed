"""房间面积上下限 — 默认推导、生成器与 pipeline 校验回归。"""

from __future__ import annotations

import pytest
from packages.schema.room import (
    DEFAULT_MAX_AREA_FACTOR,
    DEFAULT_MIN_AREA_FACTOR,
    RoomCategory,
    RoomSpec,
)
from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline


class TestRoomSpecAreaDefaults:
    def test_resolved_bounds_from_target_when_none(self) -> None:
        room = RoomSpec(id="r1", name="卫生间", category=RoomCategory.WET, target_area=4.0)
        assert room.resolved_min_area() == pytest.approx(4.0 * DEFAULT_MIN_AREA_FACTOR)
        assert room.resolved_max_area() == pytest.approx(4.0 * DEFAULT_MAX_AREA_FACTOR)

    def test_explicit_bounds_override_defaults(self) -> None:
        room = RoomSpec(
            id="r1",
            name="客厅",
            category=RoomCategory.PUBLIC,
            target_area=24.0,
            min_area=18.0,
            max_area=30.0,
        )
        assert room.resolved_min_area() == 18.0
        assert room.resolved_max_area() == 30.0


class TestPipelineAreaBounds:
    def test_top_candidates_respect_resolved_area_bounds(self) -> None:
        program = benchmark_program()
        program.solver_config.candidate_count = 64
        program.solver_config.return_top_k = 5

        bounds = {
            r.id: (r.resolved_min_area(), r.resolved_max_area()) for r in program.rooms
        }
        result = run_pipeline(program)

        assert len(result.top_candidates) >= 5, (
            f"expected at least 5 top candidates, got {len(result.top_candidates)}; "
            f"valid={result.valid} rejected={result.rejected}"
        )

        for candidate in result.top_candidates:
            assert candidate.validation is not None and candidate.validation.valid
            placement_map = {
                p.room_id: p for fl in candidate.floors for p in fl.placements
            }
            for room_id, (lo, hi) in bounds.items():
                p = placement_map.get(room_id)
                if p is None:
                    continue
                area = p.rect.area
                assert lo - 1e-6 <= area <= hi + 1e-6, (
                    f"{candidate.id} {room_id}: area={area:.2f} not in [{lo:.2f}, {hi:.2f}]"
                )

    @pytest.mark.parametrize("seed", range(51))
    def test_pipeline_seeds_0_50_top_candidates_within_bounds(self, seed: int) -> None:
        program = benchmark_program()
        program.solver_config.base_seed = seed
        program.solver_config.candidate_count = 64
        program.solver_config.return_top_k = 5

        bounds = {
            r.id: (r.resolved_min_area(), r.resolved_max_area()) for r in program.rooms
        }
        result = run_pipeline(program)

        for candidate in result.top_candidates:
            placement_map = {
                p.room_id: p for fl in candidate.floors for p in fl.placements
            }
            for room_id, (lo, hi) in bounds.items():
                p = placement_map.get(room_id)
                if p is None:
                    continue
                area = p.rect.area
                assert lo - 1e-6 <= area <= hi + 1e-6, (
                    f"seed={seed} {candidate.id} {room_id}: "
                    f"area={area:.2f} not in [{lo:.2f}, {hi:.2f}]"
                )


class TestGrowRoomsToMinArea:
    def test_undersized_room_takes_area_from_oversized_neighbor(self) -> None:
        from packages.schema.layout import PlacementRect, PlacementSource, RoomPlacement
        from solver.geometry.coverage import grow_rooms_to_min_area
        from solver.geometry.rect import Rect

        kitchen = RoomPlacement(
            room_id="r2",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=11, depth=4.5),
            source=PlacementSource.PROGRAM,
            name="厨房",
        )
        garage = RoomPlacement(
            room_id="r4",
            floor_id="F1",
            rect=PlacementRect(x=0, y=4.5, width=3.3, depth=1.9),
            source=PlacementSource.PROGRAM,
            name="车库",
        )
        footprint = Rect(x=0, y=0, width=11, depth=6.4)
        out = grow_rooms_to_min_area(
            footprint,
            [kitchen, garage],
            {"r2": 9.6, "r4": 9.0},
            {"r2": 56.0, "r4": 52.5},
        )
        by_id = {p.room_id: p for p in out}
        assert by_id["r4"].rect.area >= 9.0 - 1e-6
        assert by_id["r2"].rect.area >= 9.6 - 1e-6
        assert by_id["r2"].rect.area + by_id["r4"].rect.area <= 11 * 6.4 + 1e-6

"""湿区跨层对齐硬约束 — ADR-010 Step A 回归。"""

from __future__ import annotations

import pytest
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.room import RoomCategory, RoomSpec, SemanticRole
from packages.schema.vertical_void import (
    VerticalVoidSpec,
    VerticalVoidType,
    min_iou_for_wet_riser_tolerance,
)
from solver.evaluation.vertical import (
    DEFAULT_WET_STACK_MIN_IOU,
    min_iou_for_floor_pair,
    rect_iou,
    wet_stack_alignment_violations,
    wet_stack_pairing_key,
)
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.rect import Rect, from_placement
from solver.pipeline import run_pipeline

_FAST_SEED_SAMPLE = range(20)
_FULL_SEED_SAMPLE = range(51)


def _assert_pipeline_seeds_top_candidates_wet_stack(seed: int) -> None:
    program = benchmark_program()
    program.solver_config.base_seed = seed
    program.solver_config.candidate_count = 64
    program.solver_config.return_top_k = 5
    result = run_pipeline(program)
    for candidate in result.top_candidates:
        violations = wet_stack_alignment_violations(candidate, program)
        assert not violations, (
            f"seed={seed} {candidate.id} wet_stack: "
            f"{[v.message for v in violations]}"
        )


def _placement(
    room_id: str,
    floor_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id=floor_id,
        rect=PlacementRect(x=x, y=y, width=w, depth=h),
        source=PlacementSource.PROGRAM,
        name=room_id,
        category="wet",
    )


class TestWetStackPairingKey:
    def test_kitchen_and_bathroom_keys(self) -> None:
        kitchen = RoomSpec(
            id="r2",
            name="厨房",
            category=RoomCategory.WET,
            target_area=10,
            tags=["kitchen"],
        )
        bath = RoomSpec(id="r3", name="卫生间", category=RoomCategory.WET, target_area=4)
        master_bath = RoomSpec(
            id="r6",
            name="主卫",
            category=RoomCategory.WET,
            target_area=5,
            tags=["ensuite", "master_bath"],
        )
        assert wet_stack_pairing_key(kitchen) == SemanticRole.KITCHEN.value
        assert wet_stack_pairing_key(bath) == SemanticRole.BATHROOM.value
        assert wet_stack_pairing_key(master_bath) == SemanticRole.MASTER_BATHROOM.value


class TestWetStackAlignmentViolations:
    def test_aligned_bathroom_pair_passes(self) -> None:
        program = benchmark_program()
        candidate = LayoutCandidate(
            id="aligned",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[_placement("r3", "F1", 2, 2, 4, 3)],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[_placement("r9", "F2", 2, 2, 4, 3)],
                ),
            ],
        )
        assert not wet_stack_alignment_violations(candidate, program)

    def test_misaligned_bathroom_pair_fails(self) -> None:
        program = benchmark_program()
        candidate = LayoutCandidate(
            id="misaligned",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[_placement("r3", "F1", 0, 0, 4, 3)],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[_placement("r9", "F2", 6, 8, 4, 3)],
                ),
            ],
        )
        violations = wet_stack_alignment_violations(candidate, program)
        assert len(violations) == 1
        assert violations[0].constraint_id == "vertical.wet_stack_alignment"
        assert violations[0].hard is True
        assert "r3" in violations[0].room_ids
        assert "r9" in violations[0].room_ids

    def test_rect_iou_identical(self) -> None:
        r = Rect(x=1, y=2, width=3, depth=4)
        assert rect_iou(r, r) == pytest.approx(1.0)


class TestWetRiserToleranceMapping:
    def test_default_tolerance_maps_to_default_iou(self) -> None:
        assert min_iou_for_wet_riser_tolerance(0.3) == pytest.approx(0.6)
        assert min_iou_for_wet_riser_tolerance(0.6) == pytest.approx(0.3)

    def test_looser_tolerance_allows_partial_overlap(self) -> None:
        program = benchmark_program()
        program.vertical_voids = [
            VerticalVoidSpec(
                id="wet-riser-1",
                void_type=VerticalVoidType.WET_RISER,
                floor_span=("F1", "F2"),
                alignment_tolerance=0.6,
            )
        ]
        candidate = LayoutCandidate(
            id="partial",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[_placement("r3", "F1", 2, 2, 4, 3)],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[_placement("r9", "F2", 3.5, 2, 4, 3)],
                ),
            ],
        )
        iou = rect_iou(
            from_placement(candidate.floors[0].placements[0].rect),
            from_placement(candidate.floors[1].placements[0].rect),
        )
        assert iou < DEFAULT_WET_STACK_MIN_IOU
        assert iou >= min_iou_for_wet_riser_tolerance(0.6)
        assert not wet_stack_alignment_violations(candidate, program)

    def test_stricter_tolerance_rejects_same_pair(self) -> None:
        program = benchmark_program()
        program.vertical_voids = [
            VerticalVoidSpec(
                id="wet-riser-1",
                void_type=VerticalVoidType.WET_RISER,
                floor_span=("F1", "F2"),
                alignment_tolerance=0.15,
            )
        ]
        candidate = LayoutCandidate(
            id="partial-strict",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[_placement("r3", "F1", 2, 2, 4, 3)],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[_placement("r9", "F2", 3.5, 2, 4, 3)],
                ),
            ],
        )
        violations = wet_stack_alignment_violations(candidate, program)
        assert len(violations) == 1
        assert violations[0].required_value == pytest.approx(1.0)

    def test_floor_pair_without_wet_riser_uses_default(self) -> None:
        program = benchmark_program()
        assert min_iou_for_floor_pair(program, "F1", "F2") == pytest.approx(
            DEFAULT_WET_STACK_MIN_IOU
        )


class TestPipelineWetStackAlignment:
    def test_step_b_aligns_shared_bathroom_pair(self) -> None:
        """Step B：benchmark seed=0 的 r3↔r9 应对齐且通过湿区硬约束。"""
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        violations = wet_stack_alignment_violations(candidate, program)
        assert not violations
        f1r3 = next(p for p in candidate.floors[0].placements if p.room_id == "r3")
        f2r9 = next(p for p in candidate.floors[1].placements if p.room_id == "r9")
        assert rect_iou(from_placement(f1r3.rect), from_placement(f2r9.rect)) >= (
            DEFAULT_WET_STACK_MIN_IOU
        )

    def test_aligned_seed_passes_wet_stack(self) -> None:
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=1)
        violations = wet_stack_alignment_violations(candidate, program)
        assert not violations

    def test_pipeline_top_candidates_pass_wet_stack(self) -> None:
        program = benchmark_program()
        program.solver_config.candidate_count = 64
        program.solver_config.return_top_k = 5
        result = run_pipeline(program)

        assert len(result.top_candidates) >= 5, (
            f"expected >=5 top candidates, valid={result.valid} rejected={result.rejected}"
        )
        for candidate in result.top_candidates:
            assert candidate.validation is not None and candidate.validation.valid
            violations = wet_stack_alignment_violations(
                candidate, program, min_iou=DEFAULT_WET_STACK_MIN_IOU
            )
            assert not violations, (
                f"{candidate.id} wet_stack violations: "
                f"{[v.message for v in violations]}"
            )

    @pytest.mark.parametrize("seed", _FAST_SEED_SAMPLE)
    def test_pipeline_seeds_top_candidates_wet_stack(self, seed: int) -> None:
        _assert_pipeline_seeds_top_candidates_wet_stack(seed)


class TestPipelineWetStackAlignmentSlow:
    @pytest.mark.slow
    @pytest.mark.parametrize("seed", _FULL_SEED_SAMPLE)
    def test_pipeline_seeds_top_candidates_wet_stack_full_sample(self, seed: int) -> None:
        """51 种子大样本（pytest -m slow）。"""
        _assert_pipeline_seeds_top_candidates_wet_stack(seed)

"""ConstraintChecker 测试。"""

import pytest
from packages.schema.constraints import AdjacencyConstraint, ConstraintSource, WidthConstraint
from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from solver.constraints.checker_impl import MIN_ADJACENCY_WALL, DefaultConstraintChecker
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program

# area-bound + wet-stack 下首个 fully valid 的 benchmark seed（回归探针）
BENCHMARK_VALID_SEED = 2


def _candidate_with_two_rooms(
    *,
    a_rect: PlacementRect,
    b_rect: PlacementRect,
    same_floor: bool = True,
) -> LayoutCandidate:
    pa = RoomPlacement(
        room_id="kitchen",
        floor_id="F1",
        rect=a_rect,
        source=PlacementSource.PROGRAM,
        name="厨房",
        category="wet",
    )
    pb = RoomPlacement(
        room_id="dining",
        floor_id="F1" if same_floor else "F2",
        rect=b_rect,
        source=PlacementSource.PROGRAM,
        name="餐厅",
        category="public",
    )
    floors = [FloorLayout(floor_id="F1", placements=[pa])]
    if same_floor:
        floors[0].placements.append(pb)
    else:
        floors.append(FloorLayout(floor_id="F2", placements=[pb]))
    return LayoutCandidate(id="adj-test", seed=0, floors=floors)


def _generated_circulation(
    room_id: str,
    rect: PlacementRect,
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id="F1",
        rect=rect,
        source=PlacementSource.GENERATED,
        name="走廊",
        category="circulation",
    )


def _kitchen_dining_f1_soft_adjacency_placements() -> list[RoomPlacement]:
    """铺满 11×13 footprint；厨房与餐厅不相邻，楼梯核 1.8×4.2。"""
    return [
        _generated_circulation("stair-F1", PlacementRect(x=3.0, y=0.0, width=1.8, depth=4.2)),
        _generated_circulation("corr-mid-bottom", PlacementRect(x=4.8, y=0.0, width=3.2, depth=4.2)),
        _generated_circulation("corr-mid-top", PlacementRect(x=3.0, y=4.2, width=5.0, depth=8.8)),
        _generated_circulation("corr-west-top", PlacementRect(x=0.0, y=6.5, width=3.0, depth=6.5)),
        _generated_circulation("corr-east-top", PlacementRect(x=8.0, y=6.5, width=3.0, depth=6.5)),
        RoomPlacement(
            room_id="kitchen",
            floor_id="F1",
            rect=PlacementRect(x=0.0, y=0.0, width=3.0, depth=6.5),
            source=PlacementSource.PROGRAM,
            name="厨房",
            category="wet",
        ),
        RoomPlacement(
            room_id="dining",
            floor_id="F1",
            rect=PlacementRect(x=8.0, y=0.0, width=3.0, depth=6.5),
            source=PlacementSource.PROGRAM,
            name="餐厅",
            category="public",
        ),
    ]


def _kitchen_dining_f1_soft_separation_placements() -> list[RoomPlacement]:
    """铺满 11×13 footprint；厨房与餐厅间距 <3m，楼梯核 1.8×4.2。"""
    return [
        _generated_circulation("stair-F1", PlacementRect(x=3.0, y=0.0, width=1.8, depth=4.2)),
        _generated_circulation("corr-gap-sliver", PlacementRect(x=4.8, y=0.0, width=0.2, depth=4.2)),
        _generated_circulation("corr-gap-top", PlacementRect(x=3.0, y=4.2, width=2.0, depth=8.8)),
        _generated_circulation("corr-east", PlacementRect(x=8.0, y=0.0, width=3.0, depth=6.5)),
        _generated_circulation("corr-west-top", PlacementRect(x=0.0, y=6.5, width=3.0, depth=6.5)),
        _generated_circulation("corr-east-top", PlacementRect(x=8.0, y=6.5, width=3.0, depth=6.5)),
        RoomPlacement(
            room_id="kitchen",
            floor_id="F1",
            rect=PlacementRect(x=0.0, y=0.0, width=3.0, depth=6.5),
            source=PlacementSource.PROGRAM,
            name="厨房",
            category="wet",
        ),
        RoomPlacement(
            room_id="dining",
            floor_id="F1",
            rect=PlacementRect(x=5.0, y=0.0, width=3.0, depth=6.5),
            source=PlacementSource.PROGRAM,
            name="餐厅",
            category="public",
        ),
    ]


class TestConstraintChecker:
    def test_benchmark_has_valid_candidate(self) -> None:
        program = benchmark_program()
        checker = DefaultConstraintChecker()
        for seed in range(64):
            candidate = GuillotineGenerator().generate(program, seed=seed)
            validation = checker.check(program, candidate)
            if validation.valid:
                return
        raise AssertionError("expected at least one valid benchmark candidate in 64 seeds")

    def test_overlap_detected(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        fl = candidate.floors[0]
        dup = fl.placements[1].model_copy(deep=True)
        dup.room_id = "dup"
        fl.placements.append(dup)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any("overlap" in v.constraint_id for v in validation.hard_violations)

    def test_min_width_violation(self):
        program = benchmark_program()
        program.constraints.append(
            WidthConstraint(
                id="w-test",
                room_id="r1",
                min_width=10.0,
                source=ConstraintSource.USER,
            )
        )
        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid


class TestHardAdjacency:
    """P0-1：hard adjacency 必须使 candidate invalid。"""

    def _program_with_hard_adj(self):
        program = benchmark_program()
        program.constraints.append(
            AdjacencyConstraint(
                id="adj-kitchen-dining-hard",
                room_a_id="kitchen",
                room_b_id="dining",
                hard=True,
                source=ConstraintSource.USER,
                description="厨房必须与餐厅直接相连",
            )
        )
        return program

    def test_hard_adjacency_violation_invalidates(self):
        program = self._program_with_hard_adj()
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=5, y=0, width=3, depth=3),
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        hard_ids = [v.constraint_id for v in validation.hard_violations]
        assert "adj-kitchen-dining-hard" in hard_ids
        v = next(x for x in validation.hard_violations if x.constraint_id == "adj-kitchen-dining-hard")
        assert v.hard is True
        assert v.required_value == MIN_ADJACENCY_WALL

    def test_hard_adjacency_different_floors_invalidates(self):
        program = self._program_with_hard_adj()
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            same_floor=False,
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "adj-kitchen-dining-hard" for v in validation.hard_violations)

    def test_hard_adjacency_satisfied_when_shared_wall_enough(self):
        program = self._program_with_hard_adj()
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=3, y=0, width=3, depth=3),
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "adj-kitchen-dining-hard" for v in validation.hard_violations
        )

    @pytest.mark.skip(
        reason="手工 fixture 待改为满铺且可达的 aspect-compliant 布局"
    )
    def test_soft_adjacency_still_does_not_invalidate(self):
        from packages.schema.program import DesignProgram, SolverConfig
        from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
        from packages.schema.site import Rect2D, SiteSpec

        program = DesignProgram(
            project_id="adj-soft",
            site=SiteSpec(width=11, depth=13),
            buildable=Rect2D(x=0, y=0, width=11, depth=13),
            floors=[FloorSpec(id="F1", label="一层", room_ids=["kitchen", "dining"])],
            rooms=[
                RoomSpec(id="kitchen", name="厨房", category=RoomCategory.WET, target_area=10),
                RoomSpec(id="dining", name="餐厅", category=RoomCategory.PUBLIC, target_area=12),
            ],
            constraints=[
                AdjacencyConstraint(
                    id="adj-soft",
                    room_a_id="kitchen",
                    room_b_id="dining",
                    hard=False,
                    source=ConstraintSource.USER,
                )
            ],
            solver_config=SolverConfig(candidate_count=1),
        )
        candidate = LayoutCandidate(
            id="adj-soft",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=_kitchen_dining_f1_soft_adjacency_placements(),
                )
            ],
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid
        assert any(v.constraint_id == "adj-soft" for v in validation.soft_violations)


class TestSoftAreaWidth:
    """Soft area / width 不得被 checker 静默丢弃。"""

    def test_soft_min_width_appears_in_soft_violations(self):
        from packages.schema.constraints import WidthConstraint

        program = benchmark_program()
        program.constraints.append(
            WidthConstraint(
                id="width-soft-r1",
                room_id="r1",
                min_width=10.0,
                hard=False,
                source=ConstraintSource.USER,
            )
        )
        candidate = GuillotineGenerator().generate(program, seed=BENCHMARK_VALID_SEED)
        validation = DefaultConstraintChecker().check(program, candidate)
        soft_ids = [v.constraint_id for v in validation.soft_violations]
        assert "width-soft-r1" in soft_ids
        v = next(x for x in validation.soft_violations if x.constraint_id == "width-soft-r1")
        assert v.hard is False
        assert v.required_value == 10.0

    def test_soft_min_area_appears_in_soft_violations(self):
        from packages.schema.constraints import AreaConstraint

        program = benchmark_program()
        program.constraints.append(
            AreaConstraint(
                id="area-soft-r1",
                room_id="r1",
                min_area=500.0,
                hard=False,
                source=ConstraintSource.USER,
            )
        )
        candidate = GuillotineGenerator().generate(program, seed=BENCHMARK_VALID_SEED)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert any(v.constraint_id == "area-soft-r1" for v in validation.soft_violations)

    def test_hard_min_width_still_invalidates(self):
        program = benchmark_program()
        program.constraints.append(
            WidthConstraint(
                id="width-hard-r1",
                room_id="r1",
                min_width=10.0,
                hard=True,
                source=ConstraintSource.USER,
            )
        )
        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "width-hard-r1" for v in validation.hard_violations)


class TestProgramPlacementIntegrity:
    def test_missing_room_invalidates(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        # 去掉一个 program 房间
        for fl in candidate.floors:
            fl.placements = [
                p for p in fl.placements if p.room_id != program.rooms[0].id
            ]
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "geometry.missing_room" for v in validation.hard_violations)

    def test_duplicate_room_invalidates(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        fl = candidate.floors[0]
        prog = next(p for p in fl.placements if p.source == PlacementSource.PROGRAM)
        fl.placements.append(prog.model_copy(deep=True))
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "geometry.duplicate_room" for v in validation.hard_violations)

    def test_wrong_floor_invalidates(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        # 把 F1 的第一个 program 房间改到 F2
        f1 = candidate.floors[0]
        p = next(x for x in f1.placements if x.source == PlacementSource.PROGRAM)
        f1.placements.remove(p)
        moved = p.model_copy(deep=True)
        moved.floor_id = "F2"
        candidate.floors[1].placements.append(moved)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "geometry.wrong_floor" for v in validation.hard_violations)

    def test_unknown_room_invalidates(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        candidate.floors[0].placements.append(
            RoomPlacement(
                room_id="ghost-room",
                floor_id="F1",
                rect=PlacementRect(x=0, y=0, width=1, depth=1),
                source=PlacementSource.PROGRAM,
                name="幽灵",
                category="other",
            )
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "geometry.unknown_room" for v in validation.hard_violations)


class TestConstraintEvaluationResult:
    def test_from_violations_partitions_without_drop(self):
        from packages.schema.layout import Violation
        from solver.constraints.checker import ConstraintEvaluationResult

        violations = [
            Violation(constraint_id="h1", message="hard", hard=True),
            Violation(constraint_id="s1", message="soft", hard=False),
            Violation(constraint_id="s2", message="soft2", hard=False),
        ]
        result = ConstraintEvaluationResult.from_violations(violations)
        assert len(result.hard_violations) == 1
        assert len(result.soft_violations) == 2
        assert result.valid is False

    def test_merge_preserves_all(self):
        from packages.schema.layout import Violation
        from solver.constraints.checker import ConstraintEvaluationResult

        a = ConstraintEvaluationResult.from_violations(
            [Violation(constraint_id="h", message="h", hard=True)]
        )
        b = ConstraintEvaluationResult.from_violations(
            [Violation(constraint_id="s", message="s", hard=False)]
        )
        merged = a.merge(b)
        assert len(merged.hard_violations) == 1
        assert len(merged.soft_violations) == 1


class TestSeparationFloorAccess:
    """Phase 1.6：Separation / Floor / Access 约束 checker 接线。"""

    @staticmethod
    def _kitchen_dining_program():
        from packages.schema.program import DesignProgram, SolverConfig
        from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
        from packages.schema.site import SiteSpec

        return DesignProgram(
            project_id="chk-sep",
            site=SiteSpec(width=11, depth=13),
            buildable=SiteSpec(width=11, depth=13).buildable_envelope,
            floors=[
                FloorSpec(id="F1", label="一层", room_ids=["kitchen", "dining"]),
                FloorSpec(id="F2", label="二层", room_ids=[]),
            ],
            rooms=[
                RoomSpec(id="kitchen", name="厨房", category=RoomCategory.WET, target_area=10),
                RoomSpec(id="dining", name="餐厅", category=RoomCategory.PUBLIC, target_area=12),
            ],
            constraints=[],
            solver_config=SolverConfig(candidate_count=1),
        )

    def test_hard_separation_violation(self):
        from packages.schema.constraints import ConstraintSource, SeparationConstraint

        program = self._kitchen_dining_program()
        program.constraints.append(
            SeparationConstraint(
                id="sep-k-d",
                room_a_id="kitchen",
                room_b_id="dining",
                min_distance=3.0,
                hard=True,
                source=ConstraintSource.USER,
            )
        )
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=5, y=0, width=3, depth=3),
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "sep-k-d" for v in validation.hard_violations)

    @pytest.mark.skip(
        reason="手工 fixture 待改为满铺且可达的 aspect-compliant 布局"
    )
    def test_soft_separation_does_not_invalidate(self):
        from packages.schema.constraints import ConstraintSource, SeparationConstraint

        program = self._kitchen_dining_program()
        program.constraints.append(
            SeparationConstraint(
                id="sep-soft",
                room_a_id="kitchen",
                room_b_id="dining",
                min_distance=3.0,
                hard=False,
                source=ConstraintSource.USER,
            )
        )
        candidate = LayoutCandidate(
            id="sep-soft",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=_kitchen_dining_f1_soft_separation_placements(),
                )
            ],
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid
        assert any(v.constraint_id == "sep-soft" for v in validation.soft_violations)

    def test_hard_floor_constraint_violation(self):
        from packages.schema.constraints import ConstraintSource, FloorConstraint

        program = self._kitchen_dining_program()
        program.constraints.append(
            FloorConstraint(
                id="floor-k-f1",
                room_id="kitchen",
                floor_id="F2",
                hard=True,
                source=ConstraintSource.USER,
            )
        )
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=3, y=0, width=3, depth=3),
            same_floor=False,
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(v.constraint_id == "floor-k-f1" for v in validation.hard_violations)

    def test_separation_different_floor_not_violation(self):
        """跨层房间：SeparationConstraint 不适用，不得因平面投影距离误报。"""
        from packages.schema.constraints import ConstraintSource, SeparationConstraint

        program = self._kitchen_dining_program()
        program.constraints.append(
            SeparationConstraint(
                id="sep-cross",
                room_a_id="kitchen",
                room_b_id="dining",
                min_distance=3.0,
                hard=True,
                source=ConstraintSource.USER,
            )
        )
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            same_floor=False,
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        all_violations = validation.hard_violations + validation.soft_violations
        assert not any(v.constraint_id == "sep-cross" for v in all_violations)

    def test_upper_floor_unreachable_without_stair(self):
        """上层房间无楼梯时由 RealizedAccessGraph 统一校验，非 has_stair 启发式。"""
        program = self._kitchen_dining_program()
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=3, y=0, width=3, depth=3),
            same_floor=False,
        )
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid
        assert any(
            v.constraint_id == "access.unreachable_room" and "dining" in v.room_ids
            for v in validation.hard_violations
        )

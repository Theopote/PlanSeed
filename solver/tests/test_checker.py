"""ConstraintChecker 测试。"""

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


class TestConstraintChecker:
    def test_valid_benchmark_passes(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid

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
        candidate = _candidate_with_two_rooms(
            a_rect=PlacementRect(x=0, y=0, width=3, depth=3),
            b_rect=PlacementRect(x=5, y=0, width=3, depth=3),
        )
        # 合成候选补楼梯核，避免 geometry.core_missing 干扰 soft adj 断言
        candidate.floors[0].placements.insert(
            0,
            RoomPlacement(
                room_id="stair-F1",
                floor_id="F1",
                rect=PlacementRect(x=9.0, y=0.0, width=1.8, depth=4.2),
                source=PlacementSource.GENERATED,
                name="楼梯",
                category="circulation",
            ),
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
        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid  # soft 不 invalid
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
        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid
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

"""ConstraintChecker 测试。"""

from packages.schema.constraints import ConstraintSource, WidthConstraint
from packages.schema.layout import PlacementRect, RoomPlacement
from packages.schema.program import DesignProgram
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.tests.test_guillotine import benchmark_program


class TestConstraintChecker:
    def test_valid_benchmark_passes(self):
        program = benchmark_program()
        from solver.generators.guillotine import GuillotineGenerator

        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert validation.valid

    def test_overlap_detected(self):
        program = benchmark_program()
        from solver.generators.guillotine import GuillotineGenerator

        candidate = GuillotineGenerator().generate(program, seed=0)
        fl = candidate.floors[0]
        # 复制一个房间造成重叠
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
        from solver.generators.guillotine import GuillotineGenerator

        candidate = GuillotineGenerator().generate(program, seed=0)
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not validation.valid

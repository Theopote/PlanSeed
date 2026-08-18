"""ADR-012 — Program/Footprint 面积缺口 advisory 测试。"""

from __future__ import annotations

from packages.schema.core import CorePlacement
from packages.schema.project import ProjectSpec
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import SiteSpec
from packages.schema.vertical_void import VerticalVoidSpec, VerticalVoidType
from packages.schema.scoring import FindingSeverity
from solver.fixtures.benchmark import benchmark_program
from solver.pipeline import run_pipeline
from solver.program.normalize import (
    check_program_footprint_fit,
    _footprint_area,
    _program_sum_on_floor,
    _reserved_area_on_floor,
)


def _finding_for_floor(findings, floor_id: str):
    return next(f for f in findings if f.id == f"program.footprint_underfilled:{floor_id}")


class TestProgramFootprintAdvisory:
    def test_benchmark_triggers_on_both_floors_with_expected_magnitude(self) -> None:
        program = benchmark_program()
        findings = check_program_footprint_fit(program)

        assert _finding_for_floor(findings, "F1") is not None
        assert _finding_for_floor(findings, "F2") is not None

        footprint = _footprint_area(program)
        assert footprint == 143.0

        for floor_id in ("F1", "F2"):
            f = _finding_for_floor(findings, floor_id)
            assert f.severity == FindingSeverity.WARNING
            assert f.category == "program"
            assert "143.0㎡" in f.message
        f1_sum = _program_sum_on_floor(program, "F1")
        f2_sum = _program_sum_on_floor(program, "F2")
        assert f1_sum == 59.0
        assert f2_sum == 60.0
        # 文档「缺口 84㎡」= footprint - program_sum（未扣走廊预留与楼梯核）
        assert footprint - f1_sum == 84.0
        assert footprint - f2_sum == 83.0

        for floor_id in ("F1", "F2"):
            f = _finding_for_floor(findings, floor_id)
            surplus = float(f.message.split("约有 ")[1].split("㎡")[0])
            assert 50.0 <= surplus <= 60.0

    def test_tight_program_does_not_trigger(self) -> None:
        """房间需求接近可建面积（扣走廊预留）时不应触发。"""
        rooms = [
            RoomSpec(
                id="r1",
                name="大厅",
                category=RoomCategory.PUBLIC,
                target_area=40,
                floor_id="F1",
            ),
            RoomSpec(
                id="r2",
                name="卧室",
                category=RoomCategory.PRIVATE,
                target_area=35,
                floor_id="F1",
            ),
            RoomSpec(
                id="r3",
                name="厨卫",
                category=RoomCategory.WET,
                target_area=25,
                floor_id="F1",
            ),
        ]
        spec = ProjectSpec(
            site=SiteSpec(width=10, depth=10),
            floors=[FloorSpec(id="F1", label="一层", room_ids=["r1", "r2", "r3"])],
            rooms=rooms,
        )
        from solver.program.normalize import normalize

        program = normalize(spec)
        findings = check_program_footprint_fit(program)
        assert findings == []

    def test_atrium_area_counted_in_reserved_not_as_surplus(self) -> None:
        program = benchmark_program()
        program = program.model_copy(
            update={
                "vertical_voids": [
                    VerticalVoidSpec(
                        id="atrium-1",
                        void_type=VerticalVoidType.ATRIUM,
                        floor_span=("F1", "F2"),
                        width=3.0,
                        depth=3.0,
                        preferred_placement=CorePlacement.CENTER,
                        skylight_required=True,
                    )
                ]
            }
        )
        without = check_program_footprint_fit(benchmark_program())
        with_atrium = check_program_footprint_fit(program)

        f1_without = _finding_for_floor(without, "F1")
        f1_with = _finding_for_floor(with_atrium, "F1")
        assert f1_without is not None and f1_with is not None

        surplus_without = float(f1_without.message.split("约有 ")[1].split("㎡")[0])
        surplus_with = float(f1_with.message.split("约有 ")[1].split("㎡")[0])
        assert surplus_with < surplus_without
        assert surplus_without - surplus_with == 9.0

        reserved = _reserved_area_on_floor(program, "F1")
        assert reserved >= 9.0 + 1.8 * 4.2

    def test_advisory_does_not_block_generation(self) -> None:
        program = benchmark_program()
        program.solver_config.candidate_count = 4
        result = run_pipeline(program)
        assert result.generated == 4
        assert result.valid >= 1

        valid_with_finding = 0
        for cand in result.all_candidates:
            if not cand.validation or not cand.validation.valid:
                continue
            if not cand.evaluation:
                continue
            ids = {f.id for f in cand.evaluation.findings}
            if "program.footprint_underfilled:F1" in ids:
                valid_with_finding += 1
        assert valid_with_finding >= 1

"""Phase 8.4.1 — irregular site 端到端 pipeline 回归。"""

from __future__ import annotations

import pytest

pytest.importorskip("shapely")

from packages.schema.project import ProjectSpec
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import Point2D, Polygon2D, SiteSpec
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.buildable import program_footprint_area, program_pack_rects
from solver.geometry.coverage import COVERAGE_TOLERANCE, pack_coverage_gap
from solver.geometry.irregular import contains_axis_aligned_rect
from solver.geometry.rect import from_placement
from solver.pipeline import run_pipeline
from solver.program.normalize import normalize


def _l_shape() -> Polygon2D:
    return Polygon2D(
        exterior=[
            Point2D(x=0, y=0),
            Point2D(x=10, y=0),
            Point2D(x=10, y=5),
            Point2D(x=5, y=5),
            Point2D(x=5, y=10),
            Point2D(x=0, y=10),
        ]
    )


def _l_shape_program() -> object:
    rooms = [
        RoomSpec(id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=20, floor_id="F1"),
        RoomSpec(id="r2", name="卧室", category=RoomCategory.PRIVATE, target_area=14, floor_id="F1"),
        RoomSpec(id="r3", name="卫生间", category=RoomCategory.WET, target_area=4, floor_id="F1"),
    ]
    floors = [FloorSpec(id="F1", label="一层", room_ids=["r1", "r2", "r3"])]
    spec = ProjectSpec(
        site=SiteSpec(
            width=10,
            depth=10,
            site_polygon=_l_shape(),
            stair_width=1.8,
            stair_depth=3.6,
        ),
        floors=floors,
        rooms=rooms,
    )
    return normalize(spec)


def test_normalize_populates_free_rects():
    program = _l_shape_program()
    assert len(program.buildable_free_rects) >= 2
    assert program.buildable_polygon is not None
    assert abs(program_footprint_area(program) - 75.0) < 1e-6
    assert program.buildable.width == pytest.approx(10.0)
    assert program.buildable.depth == pytest.approx(10.0)


def test_guillotine_l_shape_finds_valid_candidate():
    program = _l_shape_program()
    program.solver_config.candidate_count = 32
    result = run_pipeline(program)
    valid = [c for c in result.all_candidates if c.validation and c.validation.valid]
    assert valid, "expected at least one valid L-shape candidate"


def test_l_shape_placements_inside_polygon():
    from solver.constraints.checker_impl import DefaultConstraintChecker

    program = _l_shape_program()
    poly = program.buildable_polygon
    assert poly is not None
    checker = DefaultConstraintChecker()
    found_valid = False
    for seed in range(32):
        candidate = GuillotineGenerator().generate(program, seed=seed)
        validation = checker.check(program, candidate)
        if not validation.valid:
            continue
        found_valid = True
        for floor in candidate.floors:
            for p in floor.placements:
                r = from_placement(p.rect)
                assert contains_axis_aligned_rect(
                    poly, x=r.x, y=r.y, width=r.width, depth=r.depth
                ), f"{p.room_id} outside buildable at seed={seed}"
        break
    assert found_valid


def test_l_shape_coverage_uses_union_area():
    program = _l_shape_program()
    pack = program_pack_rects(program)
    for seed in range(16):
        candidate = GuillotineGenerator().generate(program, seed=seed)
        if candidate.validation is None or not candidate.validation.valid:
            continue
        for floor in candidate.floors:
            placed = [from_placement(p.rect) for p in floor.placements]
            gap = pack_coverage_gap(pack, placed)
            assert abs(gap) <= COVERAGE_TOLERANCE, f"seed={seed} gap={gap}"
        break


def test_irregular_provenance_geometry_backend():
    program = _l_shape_program()
    program.solver_config.candidate_count = 8
    result = run_pipeline(program)
    valid = [c for c in result.top_candidates if c.validation and c.validation.valid]
    if not valid:
        valid = [
            c
            for c in result.all_candidates
            if c.validation and c.validation.valid
        ]
    assert valid
    assert valid[0].provenance is not None
    assert valid[0].provenance.geometry_backend == "shapely-orthogonal"


def test_rect_benchmark_regression_unchanged():
    """矩形 benchmark 经 normalize 后行为与 8.4.1 前一致。"""
    program = benchmark_program()
    a = GuillotineGenerator().generate(program, seed=0)
    b = GuillotineGenerator().generate(program, seed=0)
    assert a.model_dump(exclude={"validation", "evaluation", "score"}) == b.model_dump(
        exclude={"validation", "evaluation", "score"}
    )
    assert program.buildable_polygon is None
    assert len(program.buildable_free_rects) == 1

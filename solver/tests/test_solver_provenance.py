"""SolverProvenance — Solver 2.0 完整溯源。"""

from __future__ import annotations

from packages.schema.floor_assignment import (
    FloorAssignment,
    FloorAssignmentSource,
    RoomFloorDecision,
)
from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SELECTION_VERSION,
    SOLVER_VERSION,
    selection_strategy_for,
    solver_identity,
)
from packages.schema.provenance import (
    CandidateProvenance,
    SolverProvenance,
    alpha_solver_provenance,
    assignment_strategy_for,
    build_solver_provenance,
    geometry_backend_for,
)
from packages.schema.site import Point2D, Polygon2D
from solver.fixtures.benchmark import benchmark_program
from solver.generators import GuillotineGenerator, MaxRectGenerator
from solver.pipeline import run_pipeline


def test_candidate_provenance_is_solver_provenance_alias():
    assert CandidateProvenance is SolverProvenance


def test_alpha_solver_identity_has_strategy_layer():
    ident = solver_identity()
    assert ident == {
        "solver_version": SOLVER_VERSION,
        "generator_strategy": "guillotine",
        "generator_version": GENERATOR_VERSION,
        "selection_strategy": "axis-diverse",
        "selection_version": SELECTION_VERSION,
        "evaluation_version": EVALUATION_VERSION,
        "assignment_strategy": "heuristic",
        "geometry_backend": "rect",
    }
    assert selection_strategy_for("axis") == "axis-diverse"
    assert selection_strategy_for("pareto") == "pareto"


def test_assignment_strategy_cpsat_detection():
    program = benchmark_program()
    assert assignment_strategy_for(program) == "heuristic"
    program.floor_assignment = FloorAssignment(
        decisions=[
            RoomFloorDecision(
                room_id="living",
                floor_id="F1",
                source=FloorAssignmentSource.CPSAT,
                reason="test",
            )
        ]
    )
    assert assignment_strategy_for(program) == "cpsat"


def test_geometry_backend_irregular_after_normalize():
    """normalize 接入 irregular pipeline 后 geometry_backend 为 shapely-orthogonal。"""
    from packages.schema.project import ProjectSpec
    from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
    from packages.schema.site import Point2D, Polygon2D, SiteSpec
    from solver.program.normalize import normalize

    spec = ProjectSpec(
        site=SiteSpec(
            width=10,
            depth=10,
            site_polygon=Polygon2D(
                exterior=[
                    Point2D(x=0, y=0),
                    Point2D(x=10, y=0),
                    Point2D(x=10, y=5),
                    Point2D(x=5, y=5),
                    Point2D(x=5, y=10),
                    Point2D(x=0, y=10),
                ]
            ),
        ),
        floors=[FloorSpec(id="F1", label="一层", room_ids=["r1"])],
        rooms=[
            RoomSpec(
                id="r1", name="客厅", category=RoomCategory.PUBLIC, target_area=20, floor_id="F1"
            )
        ],
    )
    program = normalize(spec)
    assert geometry_backend_for(program) == "shapely-orthogonal"
    stamped = build_solver_provenance(program=program)
    assert stamped.geometry_backend == "shapely-orthogonal"


def test_geometry_backend_is_runtime_not_input_intent():
    """有 site_polygon ≠ 已走 Shapely packing；8.4.1 前恒为 rect。"""
    program = benchmark_program()
    assert geometry_backend_for(program) == "rect"
    program.site = program.site.model_copy(
        update={
            "site_polygon": Polygon2D(
                exterior=[
                    Point2D(x=0, y=0),
                    Point2D(x=10, y=0),
                    Point2D(x=10, y=10),
                    Point2D(x=0, y=10),
                ]
            )
        }
    )
    assert geometry_backend_for(program) == "rect"
    stamped = build_solver_provenance(program=program)
    assert stamped.geometry_backend == "rect"


def test_pipeline_stamps_full_provenance():
    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 2
    result = run_pipeline(program)
    assert result.top_candidates
    for c in result.top_candidates:
        assert c.provenance is not None
        p = c.provenance
        assert p.solver_version == SOLVER_VERSION
        assert p.generator_strategy == "guillotine"
        assert p.generator_version == GENERATOR_VERSION
        assert p.selection_strategy == "axis-diverse"
        assert p.selection_version == SELECTION_VERSION
        assert p.evaluation_version == EVALUATION_VERSION
        assert p.assignment_strategy == "heuristic"
        assert p.geometry_backend == "rect"
        assert c.metrics.get("generator_strategy") == "guillotine"
        assert c.metrics.get("selection_strategy") == "axis-diverse"


def test_maxrect_stamps_generator_strategy():
    program = benchmark_program()
    cand = MaxRectGenerator().generate(program, seed=0)
    assert cand.provenance is not None
    assert cand.provenance.generator_strategy == "maxrect"
    assert cand.provenance.generator_version == "maxrect-v1"
    g = GuillotineGenerator().generate(program, seed=0)
    assert g.provenance is not None
    assert g.provenance.generator_strategy == "guillotine"


def test_build_solver_provenance_defaults():
    p = build_solver_provenance()
    assert p.generator_strategy == "guillotine"
    assert p.assignment_strategy == "heuristic"
    assert p.geometry_backend == "rect"
    assert alpha_solver_provenance().selection_strategy == "axis-diverse"

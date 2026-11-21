"""OptimizationSession 停止条件冒烟。"""

from __future__ import annotations

from packages.schema.layout import (
    CandidateValidation,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from solver.fixtures.benchmark import benchmark_program
from solver.optimization.session import run_optimization_session


def test_optimization_stops_without_patches_when_clean():
    program = benchmark_program()
    cand = LayoutCandidate(
        id="clean",
        seed=0,
        floors=[
            FloorLayout(
                floor_id="F1",
                placements=[
                    RoomPlacement(
                        room_id="r1",
                        floor_id="F1",
                        rect=PlacementRect(x=0, y=0, width=4, depth=4),
                        source=PlacementSource.PROGRAM,
                    )
                ],
            )
        ],
        validation=CandidateValidation(valid=True),
        score=80.0,
        metrics={
            "architectural_gate_pass": True,
            "private_through_count": 0,
        },
    )
    result = run_optimization_session(
        program,
        cand,
        max_rounds=2,
        candidate_budget=2,
        generate_fn=lambda _p, _l: [cand],
    )
    assert result.stopped_reason == "no_suggested_patches"
    assert result.best is not None

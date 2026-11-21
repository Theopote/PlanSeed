"""DesignCritic 证据解读。"""

from __future__ import annotations

from packages.schema.layout import (
    CandidateValidation,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from solver.critique.critic import critique_candidate
from solver.fixtures.benchmark import benchmark_program


def test_critique_suggests_private_through_patch():
    program = benchmark_program()
    cand = LayoutCandidate(
        id="c1",
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
        metrics={
            "architectural_gate_pass": True,
            "private_through_count": 2,
        },
    )
    report = critique_candidate(program, cand)
    assert any(i["code"] == "private_through" for i in report["must_fix"])
    assert report["suggested_patches"]
    assert report["suggested_patches"][0]["changes"][0]["action"] == "avoid_private_through"

"""交通面积比 + corridor_penalty 可观测扣分。"""

from __future__ import annotations

from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from solver.evaluation.circulation import (
    circulation_architecture_score,
    circulation_area_ratio,
)
from solver.fixtures.benchmark import benchmark_program


def _cand_with_circ(*, circ_area: float) -> LayoutCandidate:
    return LayoutCandidate(
        id="c",
        seed=0,
        floors=[
            FloorLayout(
                floor_id="F1",
                placements=[
                    RoomPlacement(
                        room_id="r1",
                        floor_id="F1",
                        rect=PlacementRect(x=0, y=0, width=8, depth=8),
                        source=PlacementSource.PROGRAM,
                    ),
                    RoomPlacement(
                        room_id="circ-F1-0",
                        floor_id="F1",
                        rect=PlacementRect(x=8, y=0, width=circ_area / 4.0, depth=4),
                        source=PlacementSource.GENERATED,
                        category="circulation",
                        name="走廊",
                    ),
                ],
            )
        ],
    )


def test_circulation_area_ratio_counts_generated_corridor():
    program = benchmark_program()
    cand = _cand_with_circ(circ_area=16.0)  # 4x4
    # living 64 + circ 16 = 80 → 0.2
    assert abs(circulation_area_ratio(program, cand) - 0.2) < 1e-3


def test_corridor_penalty_lowers_score_for_fat_corridors():
    metrics = {
        "reachable_ratio": 1.0,
        "through_room_count": 0.0,
        "dead_end_count": 0.0,
        "average_access_depth": 2.0,
        "circulation_area_ratio": 0.25,
    }
    base = circulation_architecture_score(metrics, corridor_penalty=1.0)
    penalized = circulation_architecture_score(metrics, corridor_penalty=1.5)
    assert penalized < base

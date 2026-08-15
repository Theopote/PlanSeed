"""外窗标注 — daylight_required 与外墙几何连接。"""

from __future__ import annotations

from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.room import RoomCategory, RoomSpec
from packages.schema.scoring import FindingSeverity
from solver.evaluation.score import CompositeEvaluator
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.topology.windows import collect_daylight_findings, place_window_openings


def _set_daylight(program, room_ids: set[str]) -> None:
    for r in program.rooms:
        r.daylight_required = r.id in room_ids


def test_daylight_room_with_exterior_wall_gets_window() -> None:
    program = benchmark_program()
    _set_daylight(program, {"r1", "r5"})
    candidate = GuillotineGenerator().generate(program, seed=0)
    place_window_openings(program, candidate)

    windows = [w for fl in candidate.floors for w in fl.window_openings]
    by_room = {w.room_id for w in windows}
    assert "r1" in by_room
    assert "r5" in by_room

    for w in windows:
        assert w.width >= 0.9 - 1e-6
        assert w.width <= 3.0 + 1e-6
        assert w.axis in ("x", "y")


def test_non_daylight_rooms_have_no_windows() -> None:
    program = benchmark_program()
    _set_daylight(program, {"r1"})
    candidate = GuillotineGenerator().generate(program, seed=0)
    place_window_openings(program, candidate)

    windows = [w for fl in candidate.floors for w in fl.window_openings]
    assert {w.room_id for w in windows} == {"r1"}


def test_interior_daylight_room_emits_finding() -> None:
    program = benchmark_program()
    program.rooms.append(
        RoomSpec(
            id="inner",
            name="内院书房",
            category=RoomCategory.OTHER,
            target_area=9,
            floor_id="F2",
            daylight_required=True,
        )
    )
    program.floors[1].room_ids.append("inner")

    # 四周不贴外墙：居中 3×3
    candidate = LayoutCandidate(
        id="c-inner",
        seed=0,
        floors=[
            FloorLayout(floor_id="F1", placements=[]),
            FloorLayout(
                floor_id="F2",
                placements=[
                    RoomPlacement(
                        room_id="inner",
                        floor_id="F2",
                        rect=PlacementRect(x=4.0, y=5.0, width=3.0, depth=3.0),
                        source=PlacementSource.PROGRAM,
                        name="内院书房",
                        category="other",
                    )
                ],
            ),
        ],
    )

    findings = place_window_openings(program, candidate)
    assert len(findings) == 1
    f = findings[0]
    assert f.id == "environment.daylight_no_exterior_wall.inner"
    assert f.category == "environment"
    assert f.severity == FindingSeverity.WARNING
    assert "inner" in f.room_ids
    assert "自然采光" in f.message
    assert not any(w.room_id == "inner" for fl in candidate.floors for w in fl.window_openings)

    eval_findings = collect_daylight_findings(program, candidate)
    assert len(eval_findings) == 1
    assert eval_findings[0].id == f.id


def test_evaluator_merges_daylight_findings() -> None:
    program = benchmark_program()
    program.rooms.append(
        RoomSpec(
            id="inner",
            name="内院书房",
            category=RoomCategory.OTHER,
            target_area=9,
            floor_id="F2",
            daylight_required=True,
        )
    )
    program.floors[1].room_ids.append("inner")
    candidate = LayoutCandidate(
        id="c-inner",
        seed=0,
        floors=[
            FloorLayout(floor_id="F1", placements=[]),
            FloorLayout(
                floor_id="F2",
                placements=[
                    RoomPlacement(
                        room_id="inner",
                        floor_id="F2",
                        rect=PlacementRect(x=4.0, y=5.0, width=3.0, depth=3.0),
                        source=PlacementSource.PROGRAM,
                        name="内院书房",
                        category="other",
                    )
                ],
            ),
        ],
    )
    place_window_openings(program, candidate)
    score = CompositeEvaluator().evaluate(program, candidate)
    ids = {f.id for f in score.findings}
    assert "environment.daylight_no_exterior_wall.inner" in ids

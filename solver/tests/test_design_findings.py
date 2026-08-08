"""Phase 3.5 — DesignFinding 可解释评价。"""

from __future__ import annotations

from packages.schema.entry import ExteriorEntryPlacement
from packages.schema.layout import (
    DoorOpening,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.scoring import FindingSeverity
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import AccessGraph
from solver.evaluation.privacy import privacy_findings
from solver.evaluation.score import CompositeEvaluator
from solver.generators.guillotine import GuillotineGenerator
from solver.tests.test_guillotine import benchmark_program


def _placement(
    room_id: str,
    *,
    x: float,
    y: float,
    w: float,
    d: float,
    cat: str,
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id="F1",
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=room_id,
        category=cat,
    )


def _door(a: str, b: str, *, x: float, y: float, axis: str = "y") -> DoorOpening:
    return DoorOpening(
        id=f"door-{a}-{b}",
        connection_id=f"{a}-{b}",
        room_a_id=a,
        room_b_id=b,
        floor_id="F1",
        x=x,
        y=y,
        width=0.9,
        axis=axis,  # type: ignore[arg-type]
        clear_width=0.9,
    )


class TestDesignFindings:
    def test_through_private_emits_problem_finding(self):
        site = SiteSpec(width=12, depth=10, entrance_edge=CardinalEdge.SOUTH)
        rooms = [
            RoomSpec(
                id="bed_a", name="卧A", category=RoomCategory.PRIVATE, target_area=12
            ),
            RoomSpec(
                id="bed_b", name="卧B", category=RoomCategory.PRIVATE, target_area=12
            ),
        ]
        floors = [FloorSpec(id="F1", label="一层", room_ids=["bed_a", "bed_b"])]
        for r in rooms:
            r.floor_id = "F1"
        program = DesignProgram(
            project_id="find-priv",
            site=site,
            buildable=site.buildable_envelope,
            floors=floors,
            rooms=rooms,
            constraints=[],
            solver_config=SolverConfig(),
            access_graph=AccessGraph(),
        )
        candidate = LayoutCandidate(
            id="bad",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[
                        _placement("bed_a", x=0, y=5, w=6, d=5, cat="private"),
                        _placement("bed_b", x=6, y=5, w=6, d=5, cat="private"),
                    ],
                )
            ],
            exterior_entry=ExteriorEntryPlacement(
                id="exterior-entry",
                edge=CardinalEdge.SOUTH,
                x=3.0,
                y=10.0,
                width=1.2,
                connected_room_ids=["bed_a"],
                on_road_edge=True,
            ),
            door_openings=[_door("bed_a", "bed_b", x=6.0, y=7.5)],
        )
        findings = privacy_findings(program, candidate)
        problems = [f for f in findings if f.severity == FindingSeverity.PROBLEM]
        assert any("private_through" in f.id for f in problems)
        assert any("穿过" in f.message for f in problems)

    def test_composite_attaches_findings_not_just_scores(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        score = CompositeEvaluator().evaluate(program, candidate)
        assert len(score.findings) >= 3
        severities = {f.severity for f in score.findings}
        assert FindingSeverity.POSITIVE in severities or FindingSeverity.INFO in severities
        # explanations 由 findings 派生，不再是「Privacy 81」式纯分数
        assert score.explanations
        assert not any(
            e.startswith("Privacy ") and e[8:].isdigit() for e in score.explanations
        )
        assert any("[" in e for e in score.explanations)
        assert candidate.metrics.get("finding_count", 0) == len(score.findings)

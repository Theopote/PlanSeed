"""Phase 3 — Architectural Evaluation MVP。"""

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
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import AccessGraph
from solver.evaluation.privacy import compute_privacy_metrics, privacy_score
from solver.evaluation.program_fit import (
    compute_program_fit_metrics,
    compute_space_efficiency_metrics,
)
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
    floor_id: str = "F1",
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id=floor_id,
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=room_id,
        category=cat,
    )


def _door(a: str, b: str, *, x: float, y: float, axis: str = "x") -> DoorOpening:
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


class TestPrivacyEvaluator:
    def test_public_to_private_via_hall_scores_high(self):
        """entry→living→hall→bed：理想隐私过渡。"""
        site = SiteSpec(width=12, depth=10, entrance_edge=CardinalEdge.SOUTH)
        rooms = [
            RoomSpec(
                id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20
            ),
            RoomSpec(
                id="hall", name="走廊", category=RoomCategory.CIRCULATION, target_area=6
            ),
            RoomSpec(
                id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12
            ),
        ]
        floors = [
            FloorSpec(id="F1", label="一层", room_ids=["living", "hall", "bed"])
        ]
        for r in rooms:
            r.floor_id = "F1"
        program = DesignProgram(
            project_id="priv-good",
            site=site,
            buildable=site.buildable_envelope,
            floors=floors,
            rooms=rooms,
            constraints=[],
            solver_config=SolverConfig(),
            access_graph=AccessGraph(),
        )
        living = _placement("living", x=0, y=5, w=6, d=5, cat="public")
        hall = _placement("hall", x=6, y=5, w=2, d=5, cat="circulation")
        bed = _placement("bed", x=8, y=5, w=4, d=5, cat="private")
        candidate = LayoutCandidate(
            id="good",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[living, hall, bed])],
            exterior_entry=ExteriorEntryPlacement(
                id="exterior-entry",
                edge=CardinalEdge.SOUTH,
                x=3.0,
                y=10.0,
                width=1.2,
                connected_room_ids=["living"],
                on_road_edge=True,
            ),
            door_openings=[
                _door("living", "hall", x=6.0, y=7.5, axis="y"),
                _door("hall", "bed", x=8.0, y=7.5, axis="y"),
            ],
        )
        m = compute_privacy_metrics(program, candidate)
        assert m["private_through_count"] == 0
        assert float(m["privacy_transition_score"]) >= 0.85
        assert privacy_score(m) >= 85.0

    def test_through_private_bedroom_penalized(self):
        """entry→bed_a→bed_b：穿卧室到达。"""
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
            project_id="priv-bad",
            site=site,
            buildable=site.buildable_envelope,
            floors=floors,
            rooms=rooms,
            constraints=[],
            solver_config=SolverConfig(),
            access_graph=AccessGraph(),
        )
        a = _placement("bed_a", x=0, y=5, w=6, d=5, cat="private")
        b = _placement("bed_b", x=6, y=5, w=6, d=5, cat="private")
        candidate = LayoutCandidate(
            id="bad",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[a, b])],
            exterior_entry=ExteriorEntryPlacement(
                id="exterior-entry",
                edge=CardinalEdge.SOUTH,
                x=3.0,
                y=10.0,
                width=1.2,
                connected_room_ids=["bed_a"],
                on_road_edge=True,
            ),
            door_openings=[_door("bed_a", "bed_b", x=6.0, y=7.5, axis="y")],
        )
        m = compute_privacy_metrics(program, candidate)
        assert int(m["private_through_count"]) >= 1
        assert privacy_score(m) < 85.0


class TestProgramFitAndComposite:
    def test_program_fit_full_coverage(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        fit = compute_program_fit_metrics(program, candidate)
        assert fit["program_coverage"] == 1.0
        assert 0.0 < fit["program_fit"] <= 1.0
        eff = compute_space_efficiency_metrics(program, candidate)
        assert 0.0 < eff["space_efficiency"] <= 1.0

    def test_composite_exposes_phase3_breakdown(self):
        program = benchmark_program()
        candidate = GuillotineGenerator().generate(program, seed=0)
        score = CompositeEvaluator().evaluate(program, candidate)
        assert score.program_fit_score > 0
        assert score.privacy_score >= 0
        assert score.space_efficiency_score > 0
        assert score.layout_stability_score > 0
        assert score.circulation_score > 0
        assert score.total_score > 0
        assert any("Privacy" in e or "privacy" in e.lower() for e in score.explanations)
        assert score.findings
        assert "privacy_transition_score" in candidate.metrics
        assert candidate.score == score.total_score

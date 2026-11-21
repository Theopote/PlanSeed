"""Architectural Quality Gate — 严重空间组织问题挡推荐。"""

from __future__ import annotations

import pytest
from packages.schema.entry import ExteriorEntryPlacement
from packages.schema.layout import (
    CandidateValidation,
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import (
    AccessGraph,
    RealizedConnection,
    SpaceConnectionType,
)
from solver.evaluation.architectural_gate import evaluate_architectural_gate
from solver.evaluation.score import CompositeEvaluator
from solver.optimization.rank import rank_candidates
from solver.topology.access import ENTRY_NODE_ID


def _site(w: float = 12, d: float = 12) -> SiteSpec:
    return SiteSpec(width=w, depth=d, entrance_edge=CardinalEdge.SOUTH)


def _p(
    room_id: str,
    *,
    floor_id: str,
    x: float,
    y: float,
    w: float,
    d: float,
    category: str,
    name: str | None = None,
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id=floor_id,
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=name or room_id,
        category=category,
    )


def _rc(
    cid: str,
    a: str,
    b: str,
    *,
    floor_id: str = "F1",
    ctype: SpaceConnectionType = SpaceConnectionType.DOOR,
) -> RealizedConnection:
    return RealizedConnection(
        connection_id=cid,
        a=a,
        b=b,
        type=ctype,
        floor_id=floor_id,
        source="test",
    )


def _program_two_bed_guest() -> DesignProgram:
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
        RoomSpec(id="bed1", name="主卧", category=RoomCategory.PRIVATE, target_area=14),
        RoomSpec(id="bed2", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
        RoomSpec(id="bath", name="客卫", category=RoomCategory.WET, target_area=4),
    ]
    floors = [FloorSpec(id="F1", label="一层", room_ids=[r.id for r in rooms])]
    for r in rooms:
        r.floor_id = "F1"
    return DesignProgram(
        project_id="gate-test",
        site=_site(),
        buildable=_site().buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(),
        access_graph=AccessGraph(),
    )


@pytest.fixture
def stub_realized(monkeypatch: pytest.MonkeyPatch):
    """用 candidate.realized_connections 作为唯一通行边来源。"""

    def _build(program: DesignProgram, candidate: LayoutCandidate):
        return list(candidate.realized_connections)

    monkeypatch.setattr(
        "solver.topology.access.build_realized_connections",
        _build,
    )


def _cand_with_graph(
    placements: list[RoomPlacement],
    edges: list[RealizedConnection],
    *,
    cid: str = "c",
) -> LayoutCandidate:
    return LayoutCandidate(
        id=cid,
        seed=0,
        floors=[FloorLayout(floor_id="F1", placements=placements)],
        realized_connections=edges,
        exterior_entry=ExteriorEntryPlacement(
            edge=CardinalEdge.SOUTH,
            floor_id="F1",
            x=3,
            y=0,
            connected_room_ids=["living"],
        ),
    )


class TestArchitecturalGateRules:
    def test_bedroom_chain_is_blocker(self, stub_realized: None):
        program = _program_two_bed_guest()
        living = _p("living", floor_id="F1", x=0, y=0, w=4, d=6, category="public")
        bed1 = _p("bed1", floor_id="F1", x=4, y=0, w=3, d=6, category="private")
        bed2 = _p("bed2", floor_id="F1", x=7, y=0, w=3, d=6, category="private")
        bath = _p("bath", floor_id="F1", x=10, y=0, w=2, d=6, category="wet")
        cand = _cand_with_graph(
            [living, bed1, bed2, bath],
            [
                _rc("e-l", ENTRY_NODE_ID, "living", ctype=SpaceConnectionType.EXTERIOR_ENTRY),
                _rc("l-b1", "living", "bed1"),
                _rc("b1-b2", "bed1", "bed2"),
                _rc("b2-bath", "bed2", "bath"),
            ],
        )
        gate = evaluate_architectural_gate(program, cand)
        codes = {i.code for i in gate.blockers}
        assert "bedroom_chain" in codes or "guest_bath_via_private" in codes
        assert not gate.passed

    def test_guest_bath_only_to_private_is_blocker(self, stub_realized: None):
        program = _program_two_bed_guest()
        living = _p("living", floor_id="F1", x=0, y=0, w=5, d=6, category="public")
        bed1 = _p("bed1", floor_id="F1", x=5, y=0, w=4, d=6, category="private")
        bed2 = _p("bed2", floor_id="F1", x=0, y=6, w=5, d=4, category="private")
        bath = _p("bath", floor_id="F1", x=5, y=6, w=4, d=4, category="wet")
        cand = _cand_with_graph(
            [living, bed1, bed2, bath],
            [
                _rc("e-l", ENTRY_NODE_ID, "living", ctype=SpaceConnectionType.EXTERIOR_ENTRY),
                _rc("l-b1", "living", "bed1"),
                _rc("l-b2", "living", "bed2"),
                _rc("b1-bath", "bed1", "bath"),
            ],
        )
        gate = evaluate_architectural_gate(program, cand)
        assert any(i.code == "guest_bath_via_private" for i in gate.blockers)
        assert not gate.passed

    def test_good_public_layout_passes(self, stub_realized: None):
        program = _program_two_bed_guest()
        living = _p("living", floor_id="F1", x=3, y=0, w=6, d=8, category="public")
        bed1 = _p("bed1", floor_id="F1", x=0, y=0, w=3, d=5, category="private")
        bed2 = _p("bed2", floor_id="F1", x=9, y=0, w=3, d=5, category="private")
        bath = _p("bath", floor_id="F1", x=3, y=8, w=3, d=3, category="wet")
        cand = _cand_with_graph(
            [living, bed1, bed2, bath],
            [
                _rc("e-l", ENTRY_NODE_ID, "living", ctype=SpaceConnectionType.EXTERIOR_ENTRY),
                _rc("l-b1", "living", "bed1"),
                _rc("l-b2", "living", "bed2"),
                _rc("l-bath", "living", "bath"),
            ],
        )
        gate = evaluate_architectural_gate(program, cand)
        assert gate.passed
        assert not any(i.code == "bedroom_chain" for i in gate.blockers)
        assert not any(i.code == "guest_bath_via_private" for i in gate.blockers)

    def test_sliver_is_warning_not_blocker(self, stub_realized: None):
        program = _program_two_bed_guest()
        living = _p("living", floor_id="F1", x=0, y=0, w=10, d=8, category="public")
        bed1 = _p("bed1", floor_id="F1", x=0, y=8, w=1.5, d=8, category="private")
        bed2 = _p("bed2", floor_id="F1", x=1.5, y=8, w=4, d=4, category="private")
        bath = _p("bath", floor_id="F1", x=5.5, y=8, w=4.5, d=4, category="wet")
        cand = _cand_with_graph(
            [living, bed1, bed2, bath],
            [
                _rc("e-l", ENTRY_NODE_ID, "living", ctype=SpaceConnectionType.EXTERIOR_ENTRY),
                _rc("l-b1", "living", "bed1"),
                _rc("l-b2", "living", "bed2"),
                _rc("l-bath", "living", "bath"),
            ],
            cid="sliver",
        )
        gate = evaluate_architectural_gate(program, cand)
        assert any(i.code == "sliver_room" for i in gate.warnings)
        assert not any(i.code == "sliver_room" for i in gate.blockers)


class TestEntryStairGate:
    def test_entry_stair_via_private_is_blocker(self, stub_realized: None):
        rooms = [
            RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=16),
            RoomSpec(id="bed1", name="主卧", category=RoomCategory.PRIVATE, target_area=14),
            RoomSpec(id="bed2", name="次卧", category=RoomCategory.PRIVATE, target_area=12),
        ]
        floors = [
            FloorSpec(id="F1", label="一层", room_ids=["living", "bed1"]),
            FloorSpec(id="F2", label="二层", room_ids=["bed2"]),
        ]
        rooms[0].floor_id = "F1"
        rooms[1].floor_id = "F1"
        rooms[2].floor_id = "F2"
        program = DesignProgram(
            project_id="stair-gate",
            site=_site(),
            buildable=_site().buildable_envelope,
            floors=floors,
            rooms=rooms,
            constraints=[],
            solver_config=SolverConfig(),
            access_graph=AccessGraph(),
        )
        living = _p("living", floor_id="F1", x=0, y=0, w=5, d=6, category="public")
        bed1 = _p("bed1", floor_id="F1", x=5, y=0, w=4, d=6, category="private")
        stair1 = RoomPlacement(
            room_id="stair-F1",
            floor_id="F1",
            rect=PlacementRect(x=5, y=6, width=2.5, depth=4.2),
            source=PlacementSource.GENERATED,
            name="楼梯",
            category="circulation",
        )
        bed2 = _p("bed2", floor_id="F2", x=0, y=0, w=6, d=6, category="private")
        stair2 = RoomPlacement(
            room_id="stair-F2",
            floor_id="F2",
            rect=PlacementRect(x=5, y=6, width=2.5, depth=4.2),
            source=PlacementSource.GENERATED,
            name="楼梯",
            category="circulation",
        )
        cand = LayoutCandidate(
            id="stair-priv",
            seed=0,
            floors=[
                FloorLayout(floor_id="F1", placements=[living, bed1, stair1]),
                FloorLayout(floor_id="F2", placements=[bed2, stair2]),
            ],
            realized_connections=[
                _rc("e-l", ENTRY_NODE_ID, "living", ctype=SpaceConnectionType.EXTERIOR_ENTRY),
                _rc("l-b1", "living", "bed1"),
                _rc("b1-s", "bed1", "stair-F1"),
                _rc(
                    "s-vert",
                    "stair-F1",
                    "stair-F2",
                    ctype=SpaceConnectionType.STAIR,
                    floor_id="F1",
                ),
                _rc("s-b2", "stair-F2", "bed2", floor_id="F2"),
            ],
        )
        gate = evaluate_architectural_gate(program, cand)
        assert any(i.code == "entry_stair_via_private" for i in gate.blockers)
        assert not gate.passed


class TestGateRanking:
    def test_rank_prefers_gate_pass(self):
        def _mk(cid: str, score: float, passed: bool) -> LayoutCandidate:
            c = LayoutCandidate(
                id=cid,
                seed=0,
                floors=[FloorLayout(floor_id="F1", placements=[])],
                score=score,
                validation=CandidateValidation(valid=True),
            )
            c.metrics["architectural_gate_pass"] = passed
            return c

        ranked = rank_candidates(
            [_mk("fail-high", 99.0, False), _mk("pass-low", 70.0, True)],
            top_k=1,
            min_diversity_threshold=None,
            mode="score",
        )
        assert ranked[0].id == "pass-low"

    def test_evaluator_writes_gate_metrics(self, stub_realized: None):
        program = _program_two_bed_guest()
        living = _p("living", floor_id="F1", x=3, y=0, w=6, d=8, category="public")
        bed1 = _p("bed1", floor_id="F1", x=0, y=0, w=3, d=5, category="private")
        bed2 = _p("bed2", floor_id="F1", x=9, y=0, w=3, d=5, category="private")
        bath = _p("bath", floor_id="F1", x=3, y=8, w=3, d=3, category="wet")
        cand = _cand_with_graph(
            [living, bed1, bed2, bath],
            [
                _rc("e-l", ENTRY_NODE_ID, "living", ctype=SpaceConnectionType.EXTERIOR_ENTRY),
                _rc("l-b1", "living", "bed1"),
                _rc("l-b2", "living", "bed2"),
                _rc("l-bath", "living", "bath"),
            ],
            cid="eval",
        )
        CompositeEvaluator().evaluate(program, cand)
        assert "architectural_gate_pass" in cand.metrics
        assert cand.metrics["architectural_gate_version"] == "arch-gate-v1"
        assert cand.metrics["evaluation_version"] == "residential-alpha-v2"

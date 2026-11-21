"""楼梯核身份 — 禁止 circ-* / 普通 circulation 冒充楼梯。"""

from __future__ import annotations

from packages.schema.layout import (
    FloorLayout,
    LayoutCandidate,
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.program import DesignProgram, SolverConfig
from packages.schema.room import FloorSpec, RoomCategory, RoomSpec
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import SpaceConnectionType
from solver.circulation.stair_identity import (
    is_stair_core_placement,
    stair_core_placements,
)
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.topology.access import build_realized_connections


def _rect(x: float, y: float, w: float = 2.5, d: float = 4.2) -> PlacementRect:
    return PlacementRect(x=x, y=y, width=w, depth=d)


def _p(
    room_id: str,
    *,
    floor_id: str,
    rect: PlacementRect,
    category: str = "circulation",
    name: str | None = None,
    source: PlacementSource = PlacementSource.GENERATED,
) -> RoomPlacement:
    return RoomPlacement(
        room_id=room_id,
        floor_id=floor_id,
        rect=rect,
        source=source,
        name=name,
        category=category,
    )


def _two_floor_program() -> DesignProgram:
    site = SiteSpec(width=12, depth=12, entrance_edge=CardinalEdge.SOUTH)
    rooms = [
        RoomSpec(id="living", name="客厅", category=RoomCategory.PUBLIC, target_area=20),
        RoomSpec(id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=14),
    ]
    floors = [
        FloorSpec(id="F1", label="一层", room_ids=["living"]),
        FloorSpec(id="F2", label="二层", room_ids=["bed"]),
    ]
    rooms[0].floor_id = "F1"
    rooms[1].floor_id = "F2"
    return DesignProgram(
        project_id="stair-id",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        solver_config=SolverConfig(),
    )


class TestStairIdentity:
    def test_circ_fragment_is_not_stair(self):
        circ = _p("circ-F1-0", floor_id="F1", rect=_rect(0, 0), name="走廊")
        assert not is_stair_core_placement(circ)

    def test_stair_prefix_is_stair(self):
        stair = _p("stair-F1", floor_id="F1", rect=_rect(0, 0), name="楼梯")
        assert is_stair_core_placement(stair)

    def test_named_circulation_stair_is_stair(self):
        named = _p("core-1", floor_id="F1", rect=_rect(0, 0), name="楼梯核")
        assert is_stair_core_placement(named)

    def test_stair_core_placements_prefers_stair_over_circ(self):
        circ = _p("circ-F1-0", floor_id="F1", rect=_rect(0, 0), name="走廊")
        stair = _p("stair-F1", floor_id="F1", rect=_rect(3, 0), name="楼梯")
        # 走廊在前：旧逻辑会误选 circulation[0]
        got = stair_core_placements([circ, stair])
        assert [p.room_id for p in got] == ["stair-F1"]


class TestNoFalseStairConnections:
    def test_aligned_corridors_do_not_create_stair(self):
        """两层同尺寸走廊不得产生 STAIR 边。"""
        rect = _rect(1, 1, 2.5, 4.2)
        cand = LayoutCandidate(
            id="false-stair",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[
                        _p("circ-F1-0", floor_id="F1", rect=rect, name="走廊"),
                        _p(
                            "living",
                            floor_id="F1",
                            rect=_rect(4, 1, 4, 4),
                            category="public",
                            name="客厅",
                            source=PlacementSource.PROGRAM,
                        ),
                    ],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[
                        _p("circ-F2-0", floor_id="F2", rect=rect, name="走廊"),
                        _p(
                            "bed",
                            floor_id="F2",
                            rect=_rect(4, 1, 4, 4),
                            category="private",
                            name="卧室",
                            source=PlacementSource.PROGRAM,
                        ),
                    ],
                ),
            ],
        )
        program = _two_floor_program()
        realized = build_realized_connections(program, cand)
        stairs = [c for c in realized if c.type == SpaceConnectionType.STAIR]
        assert stairs == []

    def test_real_stairs_still_connect(self):
        rect = _rect(1, 1, 2.5, 4.2)
        program = _two_floor_program()
        cand = LayoutCandidate(
            id="real-stair",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[_p("stair-F1", floor_id="F1", rect=rect, name="楼梯")],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[_p("stair-F2", floor_id="F2", rect=rect, name="楼梯")],
                ),
            ],
        )
        realized = build_realized_connections(program, cand)
        stairs = [c for c in realized if c.type == SpaceConnectionType.STAIR]
        assert len(stairs) == 1
        assert {stairs[0].a, stairs[0].b} == {"stair-F1", "stair-F2"}

    def test_corridor_before_stair_does_not_fake_core_pass(self):
        """走廊在楼梯之前时，核校验仍应选真实楼梯尺寸。"""
        program = _two_floor_program()
        # 走廊故意用「合规章核」尺寸且排在前面；真实楼梯尺寸错误
        good = _rect(0, 0, 2.5, 4.2)
        bad = _rect(3, 0, 1.0, 1.0)
        cand = LayoutCandidate(
            id="order",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[
                        _p("circ-F1-0", floor_id="F1", rect=good, name="走廊"),
                        _p("stair-F1", floor_id="F1", rect=bad, name="楼梯"),
                    ],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[
                        _p("circ-F2-0", floor_id="F2", rect=good, name="走廊"),
                        _p("stair-F2", floor_id="F2", rect=bad, name="楼梯"),
                    ],
                ),
            ],
        )
        result = DefaultConstraintChecker()._check_stair_core(program, cand)
        assert any(v.constraint_id == "geometry.core_size" for v in result.hard_violations)

    def test_corridor_only_still_reports_core_missing(self):
        program = _two_floor_program()
        good = _rect(0, 0, 2.5, 4.2)
        cand = LayoutCandidate(
            id="no-stair",
            seed=0,
            floors=[
                FloorLayout(
                    floor_id="F1",
                    placements=[_p("circ-F1-0", floor_id="F1", rect=good, name="走廊")],
                ),
                FloorLayout(
                    floor_id="F2",
                    placements=[_p("circ-F2-0", floor_id="F2", rect=good, name="走廊")],
                ),
            ],
        )
        result = DefaultConstraintChecker()._check_stair_core(program, cand)
        assert any(v.constraint_id == "geometry.core_missing" for v in result.hard_violations)

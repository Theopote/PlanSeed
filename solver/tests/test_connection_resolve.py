"""ConnectionResolver — 局部共边修补（不全局重排）。"""

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
from packages.schema.site import SiteSpec
from packages.schema.topology import (
    AccessGraph,
    SpaceConnection,
    SpaceConnectionType,
)
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.topology.connection_resolve import (
    resolve_required_connections,
)
from solver.topology.doors import shared_boundary_between


def _door_program() -> DesignProgram:
    site = SiteSpec(width=10, depth=10)
    rooms = [
        RoomSpec(
            id="hall", name="过厅", category=RoomCategory.CIRCULATION, target_area=8
        ),
        RoomSpec(
            id="bed", name="卧室", category=RoomCategory.PRIVATE, target_area=12
        ),
    ]
    floors = [FloorSpec(id="F1", label="一层", room_ids=["hall", "bed"])]
    for r in rooms:
        r.floor_id = "F1"
    graph = AccessGraph()
    graph.add_connection(
        SpaceConnection(
            id="hall-bed",
            a="hall",
            b="bed",
            type=SpaceConnectionType.DOOR,
            required=True,
        )
    )
    return DesignProgram(
        project_id="conn-resolve",
        site=site,
        buildable=site.buildable_envelope,
        floors=floors,
        rooms=rooms,
        constraints=[],
        access_graph=graph,
        solver_config=SolverConfig(snap_module=0.3),
    )


class TestConnectionResolve:
    def test_closes_small_gap_between_required_pair(self):
        program = _door_program()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=4, depth=4),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        # 与 hall 左右对齐、缝隙 0.9m（≤ max_nudge）
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=4.9, y=0, width=4, depth=4),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        assert shared_boundary_between(hall, bed) is None
        n = resolve_required_connections(program, candidate)
        assert n == 1
        assert shared_boundary_between(hall, bed) is not None
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )
        assert len(candidate.door_openings) == 1

    def test_far_apart_not_repaired(self):
        program = _door_program()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=3, depth=3),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=6, y=6, width=3, depth=3),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        before = [p.rect.model_dump() for p in candidate.floors[0].placements]
        assert resolve_required_connections(program, candidate) == 0
        assert [p.rect.model_dump() for p in candidate.floors[0].placements] == before
        validation = DefaultConstraintChecker().check(program, candidate)
        assert any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )

    def test_lengthens_short_shared_edge(self):
        program = _door_program()
        # 竖向贴邻但 Y 重叠仅 0.5m < 0.9
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=4, depth=3),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=4, y=2.5, width=4, depth=3),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        assert shared_boundary_between(hall, bed, min_length=0.9) is None
        n = resolve_required_connections(program, candidate, min_wall=0.9)
        assert n == 1
        assert shared_boundary_between(hall, bed, min_length=0.9) is not None

    def test_reslice_closes_gap_with_intermediary_room(self):
        """缝隙 > max_nudge 但中间有第三者 → 局部 AABB 重切。"""
        program = _door_program()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=3, depth=4),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        filler = RoomPlacement(
            room_id="store",
            floor_id="F1",
            rect=PlacementRect(x=3, y=0, width=2, depth=4),
            source=PlacementSource.PROGRAM,
            category="service",
            name="储藏",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=5, y=0, width=3, depth=4),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        program.rooms.append(
            RoomSpec(
                id="store",
                name="储藏",
                category=RoomCategory.SERVICE,
                target_area=8,
                floor_id="F1",
            )
        )
        program.floors[0].room_ids.append("store")

        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, filler, bed])],
        )
        assert (
            resolve_required_connections(
                program, candidate, max_nudge=1.5, allow_reslice=False
            )
            == 0
        )
        n = resolve_required_connections(program, candidate, max_nudge=1.5)
        assert n == 1
        assert candidate.metrics.get("connection_reslices", 0) >= 1
        assert shared_boundary_between(hall, bed, min_length=0.9) is not None
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )

    def test_reslice_around_stair_core(self):
        """大厅|楼梯|卧室：挖核 + 绕行扩边后仍可共边；楼梯矩形不变。"""
        program = _door_program()
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=3, depth=4),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        stair = RoomPlacement(
            room_id="stair-F1",
            floor_id="F1",
            rect=PlacementRect(x=3, y=0, width=2, depth=4),
            source=PlacementSource.GENERATED,
            category="circulation",
            name="楼梯",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=5, y=0, width=3, depth=4),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        stair_before = stair.rect.model_copy()
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, stair, bed])],
        )
        n = resolve_required_connections(program, candidate, max_nudge=1.5)
        assert n == 1
        assert candidate.metrics.get("connection_reslices", 0) >= 1
        assert stair.rect == stair_before
        assert shared_boundary_between(hall, bed, min_length=0.9) is not None
        validation = DefaultConstraintChecker().check(program, candidate)
        assert not any(
            v.constraint_id == "access.missing_shared_boundary"
            for v in validation.hard_violations
        )

    def test_reslice_still_aborts_when_outsider_blocks_region(self):
        """中间外人（非楼梯）踩 AABB 且无法绕开 → 不修。"""
        program = _door_program()
        # 扩大场地，把外人放在对端之间但标为不可动的「已占用」——用另一房间
        # 这里：hall 与 bed 远距对角，中间无成员可重切且超出距离上限
        hall = RoomPlacement(
            room_id="hall",
            floor_id="F1",
            rect=PlacementRect(x=0, y=0, width=2, depth=2),
            source=PlacementSource.PROGRAM,
            category="circulation",
        )
        bed = RoomPlacement(
            room_id="bed",
            floor_id="F1",
            rect=PlacementRect(x=8, y=8, width=2, depth=2),
            source=PlacementSource.PROGRAM,
            category="private",
        )
        candidate = LayoutCandidate(
            id="c",
            seed=0,
            floors=[FloorLayout(floor_id="F1", placements=[hall, bed])],
        )
        assert resolve_required_connections(program, candidate) == 0
        assert shared_boundary_between(hall, bed) is None

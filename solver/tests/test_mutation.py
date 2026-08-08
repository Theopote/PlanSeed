"""Phase 4.3 Geometry Mutation Authority。"""

from __future__ import annotations

from packages.schema.layout import PlacementRect, PlacementSource, RoomPlacement
from packages.schema.locks import LayoutLocks, LockedZoneRect
from packages.schema.mutation import GeometryMutation, MutationKind
from packages.schema.zoning import ArchitecturalZone
from solver.fixtures.benchmark import benchmark_program
from solver.mutation import preview_mutation


def _pl(
    rid: str,
    floor: str,
    x: float,
    y: float,
    w: float = 3.0,
    d: float = 3.0,
) -> RoomPlacement:
    return RoomPlacement(
        room_id=rid,
        floor_id=floor,
        rect=PlacementRect(x=x, y=y, width=w, depth=d),
        source=PlacementSource.PROGRAM,
        name=rid,
        category="public",
    )


def test_preview_move_outside_buildable_rejected():
    program = benchmark_program()
    placements = [_pl("a", program.floors[0].id, 0, 0)]
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id="a",
        floor_id=program.floors[0].id,
        proposed=PlacementRect(
            x=program.buildable.width + 1,
            y=0,
            width=3,
            depth=3,
        ),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
    )
    assert not result.ok
    assert any(r.code == "mutation.outside_buildable" for r in result.reasons)


def test_preview_move_overlap_rejected():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 4, 0, 3, 3),
    ]
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id="a",
        floor_id=fid,
        proposed=PlacementRect(x=3.5, y=0, width=3, depth=3),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
    )
    assert not result.ok
    assert any(r.code == "mutation.overlap" for r in result.reasons)


def test_preview_move_zone_envelope_rejected():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [_pl("living", fid, 1, 1, 2, 2)]
    locks = LayoutLocks(
        zones=[
            LockedZoneRect(
                zone=ArchitecturalZone.DAY,
                floor_id=fid,
                x=0,
                y=0,
                width=4,
                depth=4,
                room_ids=["living"],
            )
        ]
    )
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id="living",
        floor_id=fid,
        proposed=PlacementRect(x=3.5, y=3.5, width=2, depth=2),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=locks,
        mutation=mut,
    )
    assert not result.ok
    assert any(r.code == "mutation.zone_envelope" for r in result.reasons)


def test_preview_move_ok_snaps():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [_pl("a", fid, 0, 0, 3, 3)]
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id="a",
        floor_id=fid,
        proposed=PlacementRect(x=1.14, y=0.86, width=3, depth=3),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
        snap_module=0.3,
    )
    assert result.ok
    assert result.snapped is not None
    assert abs(result.snapped.x - 1.2) < 1e-9
    assert abs(result.snapped.y - 0.9) < 1e-9


def test_preview_resize_min_edge_rejected():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [_pl("a", fid, 0, 0, 3, 3)]
    mut = GeometryMutation(
        kind=MutationKind.RESIZE,
        room_id="a",
        floor_id=fid,
        proposed=PlacementRect(x=0, y=0, width=0.6, depth=3),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
        snap_module=0.3,
    )
    assert not result.ok
    assert any(r.code == "mutation.min_edge" for r in result.reasons)


def test_preview_resize_overlap_rejected():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 4, 0, 3, 3),
    ]
    mut = GeometryMutation(
        kind=MutationKind.RESIZE,
        room_id="a",
        floor_id=fid,
        proposed=PlacementRect(x=0, y=0, width=4.5, depth=3),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
    )
    assert not result.ok
    assert any(r.code == "mutation.overlap" for r in result.reasons)


def test_preview_resize_ok_snaps_edges():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [_pl("a", fid, 0, 0, 3, 3)]
    mut = GeometryMutation(
        kind=MutationKind.RESIZE,
        room_id="a",
        floor_id=fid,
        proposed=PlacementRect(x=0.14, y=0.0, width=3.56, depth=3.0),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
        snap_module=0.3,
    )
    assert result.ok
    assert result.snapped is not None
    assert abs(result.snapped.x - 0.0) < 1e-9 or abs(result.snapped.x - 0.3) < 1e-9
    # x0 snap 0.0 or 0.3; x1=3.7 → 3.6; width accordingly
    assert result.snapped.width >= 0.9


def test_preview_resize_soft_min_width_warning():
    program = benchmark_program()
    room = program.rooms[0]
    room.min_width = 4.0
    fid = room.floor_id or program.floors[0].id
    placements = [_pl(room.id, fid, 0, 0, 3, 3)]
    mut = GeometryMutation(
        kind=MutationKind.RESIZE,
        room_id=room.id,
        floor_id=fid,
        proposed=PlacementRect(x=0, y=0, width=3, depth=3),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
    )
    assert result.ok
    assert any(w.code == "mutation.soft_min_width" for w in result.warnings)


def test_preview_move_access_impact_warning():
    program = benchmark_program()
    fid = program.floors[0].id
    # a|b 共边 3m；平移 a 离开共边
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 3, 0, 3, 3),
    ]
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id="a",
        floor_id=fid,
        # 仍贴邻但共边仅 0.6m < MIN_ACCESS_WALL
        proposed=PlacementRect(x=0, y=2.4, width=3, depth=3),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
        snap_module=0.3,
    )
    assert result.ok
    assert any(w.code == "mutation.access_impact" for w in result.warnings)


def test_preview_move_overlap_reports_conflict_id():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 4, 0, 3, 3),
    ]
    mut = GeometryMutation(
        kind=MutationKind.MOVE,
        room_id="a",
        floor_id=fid,
        proposed=PlacementRect(x=3.5, y=0, width=3, depth=3),
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
    )
    assert not result.ok
    assert "b" in result.conflict_room_ids


def test_list_shared_walls_rejects_t_junction():
    from solver.mutation.walls import list_shared_walls

    fid = "F1"
    # a|b 共竖墙；c 贴在共墙线上形成 T
    placements = [
        _pl("a", fid, 0, 0, 3, 4),
        _pl("b", fid, 3, 0, 3, 4),
        _pl("c", fid, 2, 4, 2, 2),  # 顶在 y=4，与 a/b 底边；另压 x=3 竖线
    ]
    # 调整 c 使其贴在 x=3 竖墙上（右侧贴 a 右缘）
    placements[2] = _pl("c", fid, 3, 1, 2, 2)
    walls = list_shared_walls(placements, floor_id=fid)
    ab = [w for w in walls if {w.room_a, w.room_b} == {"a", "b"}]
    assert ab == []


def test_list_shared_walls_two_rooms_ok():
    from solver.mutation.walls import list_shared_walls

    fid = "F1"
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 3, 0, 3, 3),
    ]
    walls = list_shared_walls(placements, floor_id=fid)
    assert len(walls) == 1
    assert walls[0].axis == "x"
    assert walls[0].coord == 3.0


def test_preview_adjust_wall_ok():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 3, 0, 3, 3),
    ]
    mut = GeometryMutation(
        kind=MutationKind.ADJUST_WALL,
        room_id="a",
        partner_room_id="b",
        floor_id=fid,
        wall_axis="x",
        wall_coord=3.6,
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
        snap_module=0.3,
    )
    assert result.ok
    assert result.snapped is not None
    assert result.snapped_partner is not None
    assert abs(result.snapped.width - 3.6) < 1e-9
    assert abs(result.snapped_partner.x - 3.6) < 1e-9


def test_preview_adjust_wall_min_edge_rejected():
    program = benchmark_program()
    fid = program.floors[0].id
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 3, 0, 3, 3),
    ]
    mut = GeometryMutation(
        kind=MutationKind.ADJUST_WALL,
        room_id="a",
        partner_room_id="b",
        floor_id=fid,
        wall_axis="x",
        wall_coord=0.3,  # a 宽仅 0.3
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
        snap_module=0.3,
    )
    assert not result.ok
    assert any(r.code == "mutation.min_edge" for r in result.reasons)


def test_preview_adjust_wall_third_overlap_rejected():
    program = benchmark_program()
    fid = program.floors[0].id
    # c 位于 b 内部空档；墙右移后 a 吞并该区与 c 重叠
    placements = [
        _pl("a", fid, 0, 0, 3, 3),
        _pl("b", fid, 3, 0, 3, 3),
        _pl("c", fid, 3.5, 0.5, 1.0, 2.0),
    ]
    mut = GeometryMutation(
        kind=MutationKind.ADJUST_WALL,
        room_id="a",
        partner_room_id="b",
        floor_id=fid,
        wall_axis="x",
        wall_coord=4.5,
    )
    result = preview_mutation(
        program=program,
        placements=placements,
        locks=LayoutLocks(),
        mutation=mut,
        snap_module=0.3,
    )
    assert not result.ok
    assert any(r.code == "mutation.overlap" for r in result.reasons)

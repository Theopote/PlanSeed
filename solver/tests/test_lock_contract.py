"""Lock 管线契约：校验、protected、不变式。"""

from __future__ import annotations

import pytest
from packages.schema.layout import (
    PlacementRect,
    PlacementSource,
    RoomPlacement,
)
from packages.schema.locks import LayoutLocks, LockedRoomRect, LockedZoneRect
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.rect import Rect
from solver.locks import (
    LockValidationError,
    assert_valid_layout_locks,
    check_lock_invariants,
    validate_layout_locks,
)
from solver.topology.connection_resolve import repair_connection_pair


def test_illegal_zone_rejected_by_schema():
    with pytest.raises(Exception):
        LockedZoneRect(
            zone="banana",
            floor_id="F1",
            x=0,
            y=0,
            width=3,
            depth=3,
        )


def test_validate_unknown_room_hard():
    program = benchmark_program()
    locks = LayoutLocks(
        rooms=[
            LockedRoomRect(
                room_id="no-such-room",
                floor_id=program.floors[0].id,
                x=0,
                y=0,
                width=3,
                depth=3,
            )
        ]
    )
    result = validate_layout_locks(program, locks)
    assert not result.valid
    assert any(i.code == "unknown_room" for i in result.issues)
    with pytest.raises(LockValidationError):
        assert_valid_layout_locks(program, locks)


def test_validate_wrong_floor_hard():
    program = benchmark_program()
    assert len(program.floors) >= 2
    # 找一个明确落在 F1 的房间
    rid = program.floors[0].room_ids[0]
    locks = LayoutLocks(
        rooms=[
            LockedRoomRect(
                room_id=rid,
                floor_id=program.floors[1].id,
                x=0,
                y=0,
                width=3,
                depth=3,
            )
        ]
    )
    result = validate_layout_locks(program, locks)
    assert not result.valid
    assert any(i.code == "wrong_floor" for i in result.issues)


def test_protected_room_not_nudged():
    """ConnectionResolver 不得移动 protected 房间。"""
    pa = RoomPlacement(
        room_id="a",
        floor_id="F1",
        rect=PlacementRect(x=0, y=0, width=3, depth=4),
        source=PlacementSource.PROGRAM,
        name="A",
        category="public",
    )
    pb = RoomPlacement(
        room_id="b",
        floor_id="F1",
        rect=PlacementRect(x=3.6, y=0, width=3, depth=4),
        source=PlacementSource.PROGRAM,
        name="B",
        category="public",
    )
    bounds = Rect(x=0, y=0, width=12, depth=12)
    before = (pa.rect.x, pa.rect.width, pb.rect.x, pb.rect.width)
    ok = repair_connection_pair(
        pa,
        pb,
        bounds=bounds,
        obstacles=[],
        module=0.3,
        max_nudge=1.5,
        protected_room_ids={"a"},
    )
    assert ok is False
    assert (pa.rect.x, pa.rect.width, pb.rect.x, pb.rect.width) == before


def test_lock_invariant_detects_room_move():
    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    room_id = next(
        p.room_id
        for fl in base.floors
        for p in fl.placements
        if not p.room_id.startswith("stair-")
    )
    lock = None
    for fl in base.floors:
        for p in fl.placements:
            if p.room_id == room_id:
                lock = LockedRoomRect(
                    room_id=p.room_id,
                    floor_id=p.floor_id,
                    x=p.rect.x,
                    y=p.rect.y,
                    width=p.rect.width,
                    depth=p.rect.depth,
                )
    assert lock is not None
    # 篡改几何
    for fl in base.floors:
        for p in fl.placements:
            if p.room_id == room_id:
                p.rect = PlacementRect(
                    x=p.rect.x + 0.9,
                    y=p.rect.y,
                    width=p.rect.width,
                    depth=p.rect.depth,
                )
    inv = check_lock_invariants(base, LayoutLocks(rooms=[lock]))
    assert any(v.constraint_id == "lock.room_moved" for v in inv.hard_violations)


def test_pipeline_rejects_invalid_locks():
    from solver.pipeline import run_pipeline

    program = benchmark_program()
    program.solver_config.candidate_count = 1
    program.solver_config.return_top_k = 1
    locks = LayoutLocks(
        rooms=[
            LockedRoomRect(
                room_id="ghost",
                floor_id=program.floors[0].id,
                x=0,
                y=0,
                width=2,
                depth=2,
            )
        ]
    )
    with pytest.raises(LockValidationError):
        run_pipeline(program, locks=locks)


def test_zone_member_repair_cannot_leave_envelope():
    """过程护栏：nudge 若把 zone member 推出 envelope 则回滚失败。"""
    pa = RoomPlacement(
        room_id="living",
        floor_id="F1",
        rect=PlacementRect(x=0, y=0, width=2.4, depth=3),
        source=PlacementSource.PROGRAM,
        name="客厅",
        category="public",
    )
    pb = RoomPlacement(
        room_id="dining",
        floor_id="F1",
        rect=PlacementRect(x=3.0, y=0, width=2.4, depth=3),
        source=PlacementSource.PROGRAM,
        name="餐厅",
        category="public",
    )
    # envelope 刚好罩住当前两房；闭合缝隙会改变宽度边界 → 仍应在内
    # 用更紧的 envelope：只允许 living 在 x∈[0,2.4]，dining 在 [3,5.4]
    # gap close 会把 mid 设到中间并改两侧宽度，dining.x 可能变为 < 3 → 越界
    envelopes = {
        "living": Rect(x=0, y=0, width=2.5, depth=3.5),
        "dining": Rect(x=2.9, y=0, width=2.6, depth=3.5),
    }
    before = (
        pa.rect.x,
        pa.rect.width,
        pb.rect.x,
        pb.rect.width,
    )
    ok = repair_connection_pair(
        pa,
        pb,
        bounds=Rect(x=0, y=0, width=12, depth=12),
        obstacles=[],
        module=0.3,
        max_nudge=1.5,
        zone_envelopes=envelopes,
    )
    # 要么失败并还原，要么成功且仍在 envelope 内
    from solver.locks.envelopes import placement_in_envelope

    if ok:
        assert placement_in_envelope(pa, envelopes["living"])
        assert placement_in_envelope(pb, envelopes["dining"])
    else:
        assert (
            pa.rect.x,
            pa.rect.width,
            pb.rect.x,
            pb.rect.width,
        ) == before


def test_overlapping_room_locks_rejected():
    program = benchmark_program()
    f1 = program.floors[0].id
    rids = [r for r in program.floors[0].room_ids if not r.startswith("stair")]
    assert len(rids) >= 2
    locks = LayoutLocks(
        rooms=[
            LockedRoomRect(
                room_id=rids[0], floor_id=f1, x=0, y=0, width=4, depth=4
            ),
            LockedRoomRect(
                room_id=rids[1], floor_id=f1, x=1, y=1, width=4, depth=4
            ),
        ]
    )
    result = validate_layout_locks(program, locks)
    assert not result.valid
    assert any(i.code == "room_lock_overlap" for i in result.issues)


def test_same_seed_and_locks_deterministic():
    program = benchmark_program()
    program.solver_config.candidate_count = 1
    base = GuillotineGenerator().generate(program, seed=0)
    room_id = next(
        p.room_id
        for fl in base.floors
        for p in fl.placements
        if not p.room_id.startswith("stair-") and fl.floor_id == program.floors[0].id
    )
    lock = None
    for fl in base.floors:
        for p in fl.placements:
            if p.room_id == room_id:
                lock = LockedRoomRect(
                    room_id=p.room_id,
                    floor_id=p.floor_id,
                    x=p.rect.x,
                    y=p.rect.y,
                    width=p.rect.width,
                    depth=p.rect.depth,
                )
    assert lock is not None
    locks = LayoutLocks(rooms=[lock])
    a = GuillotineGenerator().generate(program, seed=4, locks=locks)
    b = GuillotineGenerator().generate(program, seed=4, locks=locks)
    pa = next(p for fl in a.floors for p in fl.placements if p.room_id == room_id)
    pb = next(p for fl in b.floors for p in fl.placements if p.room_id == room_id)
    assert (pa.rect.x, pa.rect.y, pa.rect.width, pa.rect.depth) == (
        pb.rect.x,
        pb.rect.y,
        pb.rect.width,
        pb.rect.depth,
    )


def test_pipeline_sets_lock_invariant_ok():
    from solver.pipeline import run_pipeline

    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    base = GuillotineGenerator().generate(program, seed=0)
    stair = None
    for fl in base.floors:
        for p in fl.placements:
            if p.room_id.startswith("stair-"):
                from packages.schema.locks import LockedStairCore

                stair = LockedStairCore(
                    x=p.rect.x,
                    y=p.rect.y,
                    width=p.rect.width,
                    depth=p.rect.depth,
                )
                break
        if stair:
            break
    assert stair is not None
    result = run_pipeline(program, locks=LayoutLocks(stair=stair))
    for c in result.all_candidates:
        assert "lock_invariant_ok" in c.metrics
        if c.validation and c.validation.valid:
            assert c.metrics["lock_invariant_ok"] is True

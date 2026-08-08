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

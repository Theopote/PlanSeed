"""Phase 4.1 — Lock room / stair → regenerate unlocked。"""

from __future__ import annotations

from packages.schema.locks import LayoutLocks, LockedRoomRect, LockedStairCore
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.pipeline import run_pipeline


def _stair_lock_from_candidate(cand) -> LockedStairCore:
    for fl in cand.floors:
        for p in fl.placements:
            if p.room_id.startswith("stair-"):
                r = p.rect
                return LockedStairCore(
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    depth=r.depth,
                    core_placement=fl.core_placement,
                )
    raise AssertionError("no stair placement")


def _room_lock(cand, room_id: str) -> LockedRoomRect:
    for fl in cand.floors:
        for p in fl.placements:
            if p.room_id == room_id:
                r = p.rect
                return LockedRoomRect(
                    room_id=p.room_id,
                    floor_id=p.floor_id,
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    depth=r.depth,
                )
    raise AssertionError(f"no placement for {room_id}")


def test_locked_stair_stays_fixed():
    program = benchmark_program()
    program.solver_config.candidate_count = 4
    program.solver_config.return_top_k = 2
    base = GuillotineGenerator().generate(program, seed=0)
    stair = _stair_lock_from_candidate(base)
    locks = LayoutLocks(stair=stair)
    again = GuillotineGenerator().generate(program, seed=99, locks=locks)
    locked = next(
        p for fl in again.floors for p in fl.placements if p.room_id.startswith("stair-")
    )
    assert locked.rect.x == stair.x
    assert locked.rect.y == stair.y
    assert locked.rect.width == stair.width
    assert locked.rect.depth == stair.depth
    assert again.metrics.get("stair_locked") is True


def test_locked_room_stays_fixed():
    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    # 挑一个非楼梯房间
    room_id = next(
        p.room_id
        for fl in base.floors
        for p in fl.placements
        if not p.room_id.startswith("stair-")
    )
    lock = _room_lock(base, room_id)
    locks = LayoutLocks(rooms=[lock])
    again = GuillotineGenerator().generate(program, seed=3, locks=locks)
    pinned = next(
        p for fl in again.floors for p in fl.placements if p.room_id == room_id
    )
    assert pinned.rect.x == lock.x
    assert pinned.rect.y == lock.y
    assert pinned.rect.width == lock.width
    assert pinned.rect.depth == lock.depth
    assert again.metrics.get("locked_room_count") == 1


def test_pipeline_accepts_locks():
    program = benchmark_program()
    program.solver_config.candidate_count = 2
    program.solver_config.return_top_k = 1
    base = GuillotineGenerator().generate(program, seed=0)
    locks = LayoutLocks(stair=_stair_lock_from_candidate(base))
    result = run_pipeline(program, locks=locks)
    assert result.generated == 2

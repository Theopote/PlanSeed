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


def test_locked_zone_envelope_stays_fixed():
    """锁定 day 区后，该层 day 容器几何不变；区内房间仍可重排。"""
    from packages.schema.locks import LockedZoneRect

    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    assert base.zone_placements
    # 取一层有 day 的分区
    day = next((z for z in base.zone_placements if z.zone == "day"), None)
    if day is None:
        day = base.zone_placements[0]
    lock = LockedZoneRect(
        zone=day.zone,
        floor_id=day.floor_id,
        x=day.rect.x,
        y=day.rect.y,
        width=day.rect.width,
        depth=day.rect.depth,
        room_ids=list(day.room_ids),
    )
    locks = LayoutLocks(zones=[lock])
    again = GuillotineGenerator().generate(program, seed=7, locks=locks)
    pinned = next(
        z
        for z in again.zone_placements
        if z.zone == lock.zone and z.floor_id == lock.floor_id
    )
    assert pinned.rect.x == lock.x
    assert pinned.rect.y == lock.y
    assert pinned.rect.width == lock.width
    assert pinned.rect.depth == lock.depth
    assert again.metrics.get("locked_zone_count") == 1
    # 区内房间仍在 envelope 内（允许边界贴合）
    for rid in lock.room_ids:
        pl = next(
            (
                p
                for fl in again.floors
                for p in fl.placements
                if p.room_id == rid
            ),
            None,
        )
        if pl is None:
            continue
        assert pl.rect.x >= lock.x - 1e-6
        assert pl.rect.y >= lock.y - 1e-6
        assert pl.rect.right <= lock.x + lock.width + 1e-6
        assert pl.rect.bottom <= lock.y + lock.depth + 1e-6

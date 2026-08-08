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


def _overlap_area(a: Rect, b: Rect) -> float:
    x0 = max(a.x, b.x)
    y0 = max(a.y, b.y)
    x1 = min(a.x + a.width, b.x + b.width)
    y1 = min(a.y + a.depth, b.y + b.depth)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def test_room_lock_hole_is_floor_local():
    """P0：F1 房间锁不得投影到 F2 free space（楼梯核除外）。"""
    from solver.geometry.rect import Rect

    program = benchmark_program()
    assert len(program.floors) >= 2
    f1_id = program.floors[0].id
    f2_id = program.floors[1].id
    base = GuillotineGenerator().generate(program, seed=0)
    f1_rooms = [
        p
        for fl in base.floors
        if fl.floor_id == f1_id
        for p in fl.placements
        if not p.room_id.startswith("stair-")
    ]
    assert f1_rooms
    pinned = max(f1_rooms, key=lambda p: p.rect.area)
    lock = LockedRoomRect(
        room_id=pinned.room_id,
        floor_id=pinned.floor_id,
        x=pinned.rect.x,
        y=pinned.rect.y,
        width=pinned.rect.width,
        depth=pinned.rect.depth,
    )
    assert lock.floor_id == f1_id

    again = GuillotineGenerator().generate(
        program, seed=11, locks=LayoutLocks(rooms=[lock])
    )
    hole = Rect(x=lock.x, y=lock.y, width=lock.width, depth=lock.depth)
    f2_overlap = 0.0
    for fl in again.floors:
        if fl.floor_id != f2_id:
            continue
        for p in fl.placements:
            if p.room_id.startswith("stair-"):
                continue
            pr = Rect(
                x=p.rect.x, y=p.rect.y, width=p.rect.width, depth=p.rect.depth
            )
            f2_overlap += _overlap_area(pr, hole)

    assert f2_overlap > 1.0, (
        f"F2 应仍可占用 F1 锁定脚印；overlap={f2_overlap:.2f}"
    )


def test_plan_building_per_floor_free_rects():
    """ZonePlanner：各层使用各自 free_rects，不得共用另一层的洞。"""
    import random

    from packages.schema.room import RoomCategory, RoomSpec
    from solver.geometry.rect import Rect
    from solver.topology.zoning import ZonePlanner

    f1 = [
        RoomSpec(
            id="living",
            name="客厅",
            category=RoomCategory.PUBLIC,
            target_area=20,
        ),
    ]
    f2 = [
        RoomSpec(
            id="bed",
            name="主卧",
            category=RoomCategory.PRIVATE,
            target_area=18,
        ),
    ]
    # F1 左下被挖洞；F2 整板可用
    full = [Rect(x=0, y=0, width=10, depth=12)]
    f1_free = [
        Rect(x=5, y=0, width=5, depth=12),
        Rect(x=0, y=4, width=5, depth=8),
    ]
    building = ZonePlanner().plan_building(
        floors=[("F1", f1), ("F2", f2)],
        free_rects=full,
        free_rects_by_floor={"F1": f1_free, "F2": full},
        rng=random.Random(0),
    )
    f2_zones = building.floors["F2"].zones
    assert f2_zones
    # F2 分区应能盖住 F1 挖掉的 (0,0)-(5,4) 区域
    hole = Rect(x=0, y=0, width=5, depth=4)
    cover = sum(
        _overlap_area(
            Rect(z.rect.x, z.rect.y, z.rect.width, z.rect.depth), hole
        )
        for z in f2_zones
    )
    assert cover > 5.0, f"F2 zone should cover F1 hole footprint; cover={cover}"

"""Phase 4.1 — Lock room / stair → regenerate unlocked。"""

from __future__ import annotations

from packages.schema.locks import LayoutLocks, LockedRoomRect, LockedStairCore, LockedZoneRect
from solver.fixtures.benchmark import benchmark_program
from solver.generators.guillotine import GuillotineGenerator
from solver.geometry.rect import Rect
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


def _zone_envelope_key(cand, floor_id: str) -> frozenset[tuple]:
    """该层 zone envelope 快照：(zone, x, y, w, d)。"""
    return frozenset(
        (
            z.zone,
            round(z.rect.x, 6),
            round(z.rect.y, 6),
            round(z.rect.width, 6),
            round(z.rect.depth, 6),
        )
        for z in cand.zone_placements
        if z.floor_id == floor_id
    )


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


def test_zone_placement_has_stable_id():
    """ZonePlacement 带 id/kind；锁 zone_id 后 Regenerate 保持同一 id。"""
    program = benchmark_program()
    gen = GuillotineGenerator()
    base = gen.generate(program, seed=0)
    assert base.zone_placements
    z0 = base.zone_placements[0]
    assert z0.id
    assert z0.kind == z0.zone or z0.kind is None
    assert z0.id.startswith(f"{z0.floor_id}-{z0.resolved_kind()}-")

    lock = LockedZoneRect(
        zone=z0.zone,
        floor_id=z0.floor_id,
        x=z0.rect.x,
        y=z0.rect.y,
        width=z0.rect.width,
        depth=z0.rect.depth,
        room_ids=list(z0.room_ids),
        zone_id=z0.id,
    )
    again = gen.generate(program, seed=5, locks=LayoutLocks(zones=[lock]))
    pinned = next(z for z in again.zone_placements if z.id == z0.id)
    assert pinned.rect.x == z0.rect.x
    assert pinned.rect.y == z0.rect.y


def test_locked_zone_envelope_stays_fixed():
    """锁定 day 区后，该层 day 容器几何不变；区内房间仍可重排。"""
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
        zone_id=day.id,
    )
    locks = LayoutLocks(zones=[lock])
    again = GuillotineGenerator().generate(program, seed=7, locks=locks)
    if day.id:
        pinned = next(z for z in again.zone_placements if z.id == day.id)
    else:
        kind = lock.zone.value if hasattr(lock.zone, "value") else str(lock.zone)
        pinned = next(
            z
            for z in again.zone_placements
            if z.zone == kind and z.floor_id == lock.floor_id
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


def test_room_lock_is_floor_local():
    """P0：F1 房间锁不得影响同 seed 下的 F2 zone envelope。"""
    program = benchmark_program()
    assert len(program.floors) >= 2
    f1_id = program.floors[0].id
    f2_id = program.floors[1].id
    gen = GuillotineGenerator()

    # 从 seed=0 取 F1 大房间作锁几何（与对比 seed 解耦）
    base = gen.generate(program, seed=0)
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

    seed = 11
    unlocked = gen.generate(program, seed=seed)
    locked_f1 = gen.generate(program, seed=seed, locks=LayoutLocks(rooms=[lock]))

    free_f2 = _zone_envelope_key(unlocked, f2_id)
    locked_f2 = _zone_envelope_key(locked_f1, f2_id)
    assert free_f2, "无锁方案应有 F2 zone"
    assert free_f2 == locked_f2, (
        "仅锁 F1 时 F2 zone envelope 必须与无锁相同；"
        f"free={sorted(free_f2)} locked={sorted(locked_f2)}"
    )

    # F1 被锁房间几何仍钉死
    pinned_again = next(
        p
        for fl in locked_f1.floors
        for p in fl.placements
        if p.room_id == lock.room_id
    )
    assert pinned_again.rect.x == lock.x
    assert pinned_again.rect.y == lock.y
    assert pinned_again.rect.width == lock.width
    assert pinned_again.rect.depth == lock.depth


def _overlap_area(a: Rect, b: Rect) -> float:
    x0 = max(a.x, b.x)
    y0 = max(a.y, b.y)
    x1 = min(a.x + a.width, b.x + b.width)
    y1 = min(a.y + a.depth, b.y + b.depth)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def test_plan_building_per_floor_free_rects():
    """ZonePlanner：各层使用各自 free_rects，不得共用另一层的洞。"""
    import random

    from packages.schema.room import RoomCategory, RoomSpec
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

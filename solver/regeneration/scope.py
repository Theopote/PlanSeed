"""RegenerationScope → LayoutLocks 解析。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, PlacementSource
from packages.schema.locks import LayoutLocks, LockedRoomRect, LockedStairCore
from packages.schema.program import DesignProgram
from packages.schema.regeneration import RegenerationScope

from solver.circulation.stair_identity import is_stair_core_room_id
from solver.regeneration.errors import RegenerationScopeError
from solver.topology.graph import build_graph_from_program, neighbors

_GEOM_TOL = 1e-3


def derive_affected_neighbors(
    program: DesignProgram,
    mutable_room_ids: list[str],
) -> list[str]:
    """从 RoomGraph 推导 mutable 房间的一阶邻接（不含 mutable 自身）。"""
    graph = build_graph_from_program(program)
    mutable = set(mutable_room_ids)
    found: set[str] = set()
    for rid in mutable_room_ids:
        for n in neighbors(graph, rid):
            if n not in mutable:
                found.add(n)
    return sorted(found)


def enrich_regeneration_scope(
    scope: RegenerationScope,
    program: DesignProgram,
) -> RegenerationScope:
    """填充 affected_neighbors（若调用方未提供）。"""
    if scope.affected_neighbors:
        return scope
    return scope.model_copy(
        update={
            "affected_neighbors": derive_affected_neighbors(
                program, scope.mutable_rooms
            )
        }
    )


def resolve_locked_room_ids(
    scope: RegenerationScope,
    program: DesignProgram,
) -> set[str]:
    """根据 scope 计算应钉死的 program 房间 id。"""
    program_ids = {r.id for r in program.rooms}
    mutable = scope.mutable_room_ids
    unknown_mutable = mutable - program_ids
    if unknown_mutable:
        raise RegenerationScopeError(
            f"mutable_rooms 不在 program 中：{sorted(unknown_mutable)}",
            code="unknown_mutable_rooms",
            room_ids=sorted(unknown_mutable),
        )

    if scope.locked_rooms:
        locked = scope.locked_room_ids - mutable
        unknown_locked = locked - program_ids
        if unknown_locked:
            raise RegenerationScopeError(
                f"locked_rooms 不在 program 中：{sorted(unknown_locked)}",
                code="unknown_locked_rooms",
                room_ids=sorted(unknown_locked),
            )
    else:
        locked = program_ids - mutable

    return locked


def _program_floor_by_room(program: DesignProgram) -> dict[str, str]:
    out: dict[str, str] = {}
    for fl in program.floors:
        for rid in fl.room_ids:
            out[rid] = fl.id
    for room in program.rooms:
        if room.id not in out and room.floor_id:
            out[room.id] = room.floor_id
    return out


def _assert_preserve_floor_assignment(
    scope: RegenerationScope,
    program: DesignProgram,
    room_locks: list[LockedRoomRect],
) -> None:
    if not scope.preserve_floor_assignment:
        return
    expected = _program_floor_by_room(program)
    bad: list[str] = []
    for lock in room_locks:
        want = expected.get(lock.room_id)
        if want is not None and lock.floor_id != want:
            bad.append(lock.room_id)
    if bad:
        raise RegenerationScopeError(
            f"preserve_floor_assignment：锁定房间楼层与 program 不一致：{sorted(bad)}",
            code="floor_assignment_mismatch",
            room_ids=sorted(bad),
        )


def _rects_conflict(a: LockedRoomRect, b: LockedRoomRect) -> bool:
    if a.floor_id != b.floor_id:
        return True
    return (
        abs(a.x - b.x) > _GEOM_TOL
        or abs(a.y - b.y) > _GEOM_TOL
        or abs(a.width - b.width) > _GEOM_TOL
        or abs(a.depth - b.depth) > _GEOM_TOL
    )


def _stairs_conflict(a: LockedStairCore, b: LockedStairCore) -> bool:
    return (
        abs(a.x - b.x) > _GEOM_TOL
        or abs(a.y - b.y) > _GEOM_TOL
        or abs(a.width - b.width) > _GEOM_TOL
        or abs(a.depth - b.depth) > _GEOM_TOL
    )


def merge_layout_locks(
    existing: LayoutLocks | None,
    scope_locks: LayoutLocks,
    *,
    mutable_room_ids: set[str],
) -> LayoutLocks:
    """
    以既有会话锁为基础，合并作用域派生锁。

    - 保留既有 zone 锁与楼梯元数据（无冲突时）
    - 作用域锁定房间覆盖/对齐几何；与既有房间锁冲突则拒绝
    - mutable 房间不得残留在合并后的房间锁中
    """
    base = existing or LayoutLocks()
    by_id: dict[str, LockedRoomRect] = {
        r.room_id: r for r in base.rooms if r.room_id not in mutable_room_ids
    }
    conflicts: list[str] = []
    for r in scope_locks.rooms:
        if r.room_id in mutable_room_ids:
            continue
        prev = by_id.get(r.room_id)
        if prev is not None and _rects_conflict(prev, r):
            conflicts.append(r.room_id)
            continue
        by_id[r.room_id] = r
    if conflicts:
        raise RegenerationScopeError(
            f"局部重生成与既有房间锁几何冲突：{sorted(conflicts)}",
            code="lock_geometry_conflict",
            room_ids=sorted(conflicts),
        )

    stair = base.stair
    if stair is None:
        stair = scope_locks.stair
    elif scope_locks.stair is not None and _stairs_conflict(stair, scope_locks.stair):
        raise RegenerationScopeError(
            "局部重生成与既有楼梯核锁几何冲突",
            code="stair_lock_conflict",
            room_ids=[],
        )
    elif stair.core_placement is None and scope_locks.stair is not None:
        stair = stair.model_copy(
            update={"core_placement": scope_locks.stair.core_placement}
        )

    return LayoutLocks(
        rooms=[by_id[rid] for rid in sorted(by_id)],
        stair=stair,
        zones=list(base.zones),
    )


def _placement_lock_from_candidate(
    candidate: LayoutCandidate,
    room_id: str,
) -> LockedRoomRect:
    for fl in candidate.floors:
        for p in fl.placements:
            if p.room_id == room_id and p.source == PlacementSource.PROGRAM:
                r = p.rect
                return LockedRoomRect(
                    room_id=p.room_id,
                    floor_id=p.floor_id,
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    depth=r.depth,
                )
    raise RegenerationScopeError(
        f"base candidate 无 program 房间放置：{room_id!r}",
        code="missing_base_placement",
        room_ids=[room_id],
    )


def _stair_lock_from_candidate(
    candidate: LayoutCandidate,
) -> LockedStairCore | None:
    for fl in candidate.floors:
        for p in fl.placements:
            if is_stair_core_room_id(p.room_id):
                r = p.rect
                return LockedStairCore(
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    depth=r.depth,
                    core_placement=fl.core_placement,
                )
    return None


def locks_from_regeneration_scope(
    scope: RegenerationScope,
    program: DesignProgram,
    base_candidate: LayoutCandidate,
) -> LayoutLocks:
    """
    将 RegenerationScope + 基线候选转为 LayoutLocks。

    锁定房间几何取自 base_candidate；楼梯核（若有）默认一并锁定。
    """
    enriched = enrich_regeneration_scope(scope, program)
    locked_ids = resolve_locked_room_ids(enriched, program)
    room_locks = [
        _placement_lock_from_candidate(base_candidate, rid)
        for rid in sorted(locked_ids)
    ]
    _assert_preserve_floor_assignment(enriched, program, room_locks)
    return LayoutLocks(
        rooms=room_locks,
        stair=_stair_lock_from_candidate(base_candidate),
    )


def locks_from_placement_rects(
    scope: RegenerationScope,
    program: DesignProgram,
    placements: list[LockedRoomRect],
) -> LayoutLocks:
    """API 路径：由前端提交的 placement 摘要构建 locks。"""
    enriched = enrich_regeneration_scope(scope, program)
    locked_ids = resolve_locked_room_ids(enriched, program)
    by_id: dict[str, LockedRoomRect] = {}
    for p in placements:
        if p.room_id in by_id and _rects_conflict(by_id[p.room_id], p):
            raise RegenerationScopeError(
                f"base_placements 房间重复且几何不一致：{p.room_id}",
                code="duplicate_base_placement",
                room_ids=[p.room_id],
            )
        by_id[p.room_id] = p
    missing = locked_ids - set(by_id)
    if missing:
        raise RegenerationScopeError(
            f"base_placements 缺少锁定房间：{sorted(missing)}",
            code="missing_base_placement",
            room_ids=sorted(missing),
        )
    room_locks = [by_id[rid] for rid in sorted(locked_ids)]
    _assert_preserve_floor_assignment(enriched, program, room_locks)
    stair = None
    for p in placements:
        if is_stair_core_room_id(p.room_id):
            stair = LockedStairCore(
                x=p.x,
                y=p.y,
                width=p.width,
                depth=p.depth,
            )
            break
    return LayoutLocks(rooms=room_locks, stair=stair)

"""会话锁校验 — 生成前 hard reject，禁止静默忽略。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.zoning import ArchitecturalZone
from solver.geometry.rect import Rect, intersects
from solver.topology.zoning import zone_for_room


@dataclass
class LockValidationIssue:
    code: str
    message: str
    hard: bool = True


@dataclass
class LockValidationResult:
    issues: list[LockValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(i.hard for i in self.issues)

    def add(self, code: str, message: str, *, hard: bool = True) -> None:
        self.issues.append(LockValidationIssue(code=code, message=message, hard=hard))


class LockValidationError(ValueError):
    """无效 LayoutLocks；API 应映射为 HTTP 422。"""

    def __init__(self, result: LockValidationResult):
        self.result = result
        msgs = "; ".join(i.message for i in result.issues if i.hard)
        super().__init__(msgs or "invalid layout locks")


def validate_layout_locks(
    program: DesignProgram,
    locks: LayoutLocks,
) -> LockValidationResult:
    """
    生成前一次性检查锁请求。

    Invalid request → hard（unknown / wrong_floor / illegal zone / duplicate）
    Geometrically impossible → hard（与 stair/房间/分区重叠）
    """
    out = LockValidationResult()
    if locks is None:
        return out

    room_by_id = {r.id: r for r in program.rooms}
    floor_ids = {fl.id for fl in program.floors}
    expected_floor: dict[str, str] = {}
    for fl in program.floors:
        for rid in fl.room_ids:
            expected_floor[rid] = fl.id
    for room in program.rooms:
        if room.id not in expected_floor and room.floor_id:
            expected_floor[room.id] = room.floor_id

    buildable = Rect(
        x=0.0,
        y=0.0,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )

    # —— Room locks ——
    seen_rooms: set[str] = set()
    for lr in locks.rooms:
        if lr.room_id in seen_rooms:
            out.add(
                "duplicate_room_lock",
                f"房间锁重复：{lr.room_id}",
            )
            continue
        seen_rooms.add(lr.room_id)

        if lr.room_id not in room_by_id and not lr.room_id.startswith("stair-"):
            out.add("unknown_room", f"未知房间锁：{lr.room_id}")
            continue
        if lr.floor_id not in floor_ids:
            out.add("wrong_floor", f"房间锁楼层不存在：{lr.room_id} @ {lr.floor_id}")
            continue
        exp = expected_floor.get(lr.room_id)
        if exp is not None and exp != lr.floor_id:
            out.add(
                "wrong_floor",
                f"房间 {lr.room_id} 应在 {exp}，锁写在 {lr.floor_id}",
            )
        rect = Rect(x=lr.x, y=lr.y, width=lr.width, depth=lr.depth)
        if not _contains_tol(buildable, rect):
            out.add(
                "room_lock_outside_buildable",
                f"房间锁超出可建范围：{lr.room_id}",
            )

    # —— Stair ——
    stair_rect: Rect | None = None
    if locks.stair is not None:
        stair_rect = Rect(
            x=locks.stair.x,
            y=locks.stair.y,
            width=locks.stair.width,
            depth=locks.stair.depth,
        )
        if not _contains_tol(buildable, stair_rect):
            out.add(
                "lock_core_outside_buildable",
                "楼梯核锁超出可建范围",
            )

    # —— Zones ——
    # 同 floor+kind 多条 = FunctionalZoneGroup 多组件，合法；校验每条
    zone_members: dict[tuple[str, str], set[str]] = {}
    for lz in locks.zones:
        kind: ArchitecturalZone
        if isinstance(lz.zone, ArchitecturalZone):
            kind = lz.zone
        else:
            try:
                kind = ArchitecturalZone(lz.zone)
            except ValueError:
                out.add("illegal_zone", f"非法功能分区：{lz.zone!r}")
                continue
        if kind == ArchitecturalZone.CIRCULATION:
            out.add(
                "illegal_zone",
                f"不可锁定 circulation 分区 @ {lz.floor_id}",
            )
            continue
        if lz.floor_id not in floor_ids:
            out.add("wrong_floor", f"分区锁楼层不存在：{kind.value} @ {lz.floor_id}")
            continue
        zrect = Rect(x=lz.x, y=lz.y, width=lz.width, depth=lz.depth)
        if not _contains_tol(buildable, zrect):
            out.add(
                "zone_lock_outside_buildable",
                f"分区锁超出可建范围：{kind.value} @ {lz.floor_id}",
            )
        key = (lz.floor_id, kind.value)
        bucket = zone_members.setdefault(key, set())
        for rid in lz.room_ids:
            if rid in locks.locked_room_ids:
                continue
            if rid not in room_by_id:
                out.add("unknown_room", f"分区锁含未知房间：{rid}")
                continue
            exp = expected_floor.get(rid)
            if exp is not None and exp != lz.floor_id:
                out.add(
                    "wrong_floor",
                    f"分区锁房间 {rid} 应在 {exp}，却列入 {lz.floor_id}",
                )
                continue
            z_expected = zone_for_room(room_by_id[rid])
            if z_expected != kind:
                out.add(
                    "room_zone_conflict",
                    f"房间 {rid} 属 {z_expected.value}，不可列入 {kind.value} 锁",
                )
                continue
            # 同一房间不得出现在同层另一 kind 的 zone 锁中
            for (fid, zk), members in zone_members.items():
                if fid == lz.floor_id and zk != kind.value and rid in members:
                    out.add(
                        "room_zone_conflict",
                        f"房间 {rid} 同时出现在 {zk} 与 {kind.value} 锁",
                    )
            if rid in bucket:
                out.add(
                    "duplicate_room_lock",
                    f"房间 {rid} 在分区锁 {kind.value}@{lz.floor_id} 中重复",
                )
            bucket.add(rid)

    # —— 同层 zone 组件互叠 ——
    by_floor_zones: dict[str, list[Rect]] = {}
    for lz in locks.zones:
        if isinstance(lz.zone, ArchitecturalZone):
            kind = lz.zone
        else:
            try:
                kind = ArchitecturalZone(lz.zone)
            except ValueError:
                continue
        if kind == ArchitecturalZone.CIRCULATION:
            continue
        by_floor_zones.setdefault(lz.floor_id, []).append(
            Rect(x=lz.x, y=lz.y, width=lz.width, depth=lz.depth)
        )
    for fid, rects in by_floor_zones.items():
        for i, a in enumerate(rects):
            for b in rects[i + 1 :]:
                if intersects(a, b):
                    out.add(
                        "zone_overlap",
                        f"同层分区锁重叠 @ {fid}",
                    )

    # —— room lock vs stair ——
    if stair_rect is not None:
        for lr in locks.rooms:
            rr = Rect(x=lr.x, y=lr.y, width=lr.width, depth=lr.depth)
            if intersects(rr, stair_rect):
                out.add(
                    "lock_core_overlap",
                    f"房间锁与楼梯核重叠：{lr.room_id}",
                )

    # —— 同层 room locks 互叠 ——
    rooms_by_floor: dict[str, list[tuple[str, Rect]]] = {}
    for lr in locks.rooms:
        rooms_by_floor.setdefault(lr.floor_id, []).append(
            (lr.room_id, Rect(x=lr.x, y=lr.y, width=lr.width, depth=lr.depth))
        )
    for fid, items in rooms_by_floor.items():
        for i, (ida, ra) in enumerate(items):
            for idb, rb in items[i + 1 :]:
                if intersects(ra, rb):
                    out.add(
                        "room_lock_overlap",
                        f"房间锁重叠：{ida} 与 {idb} @ {fid}",
                    )

    return out


def assert_valid_layout_locks(program: DesignProgram, locks: LayoutLocks) -> None:
    result = validate_layout_locks(program, locks)
    if not result.valid:
        raise LockValidationError(result)


def _contains_tol(outer: Rect, inner: Rect, tol: float = 1e-6) -> bool:
    return (
        inner.x >= outer.x - tol
        and inner.y >= outer.y - tol
        and inner.x + inner.width <= outer.x + outer.width + tol
        and inner.y + inner.depth <= outer.y + outer.depth + tol
    )

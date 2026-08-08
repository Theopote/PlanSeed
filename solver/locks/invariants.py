"""最终 Lock 不变式 — 后处理后仍须成立。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, Violation
from packages.schema.locks import LayoutLocks
from solver.constraints.checker import ConstraintEvaluationResult
from solver.geometry.rect import Rect


_TOL = 1e-4


def check_lock_invariants(
    candidate: LayoutCandidate,
    locks: LayoutLocks | None,
) -> ConstraintEvaluationResult:
    """
    LockedRoom / Stair / Zone envelope 相对锁请求不可变。

    Zone：envelope 几何不变，且非 Room-Lock 的成员仍在 envelope 内。
    """
    if locks is None:
        return ConstraintEvaluationResult.empty()
    violations: list[Violation] = []

    placement_by_id = {
        p.room_id: p for fl in candidate.floors for p in fl.placements
    }

    for lr in locks.rooms:
        p = placement_by_id.get(lr.room_id)
        if p is None:
            violations.append(
                Violation(
                    constraint_id="lock.room_missing",
                    room_ids=[lr.room_id],
                    message=f"锁定房间缺失：{lr.room_id}",
                    hard=True,
                    source="system",
                )
            )
            continue
        if p.floor_id != lr.floor_id:
            violations.append(
                Violation(
                    constraint_id="lock.room_moved",
                    room_ids=[lr.room_id],
                    message=(
                        f"锁定房间楼层被改：{lr.room_id} "
                        f"{lr.floor_id} → {p.floor_id}"
                    ),
                    hard=True,
                    source="system",
                )
            )
            continue
        if not _same_rect(p.rect.x, p.rect.y, p.rect.width, p.rect.depth, lr):
            violations.append(
                Violation(
                    constraint_id="lock.room_moved",
                    room_ids=[lr.room_id],
                    message=f"锁定房间几何被改动：{lr.room_id}",
                    hard=True,
                    source="system",
                )
            )

    if locks.stair is not None:
        stairs = [
            p
            for fl in candidate.floors
            for p in fl.placements
            if p.room_id.startswith("stair-")
        ]
        if not stairs:
            violations.append(
                Violation(
                    constraint_id="lock.stair_moved",
                    room_ids=[],
                    message="楼梯核锁存在但候选无楼梯放置",
                    hard=True,
                    source="system",
                )
            )
        else:
            for st in stairs:
                if not _same_rect(
                    st.rect.x,
                    st.rect.y,
                    st.rect.width,
                    st.rect.depth,
                    locks.stair,
                ):
                    violations.append(
                        Violation(
                            constraint_id="lock.stair_moved",
                            room_ids=[st.room_id],
                            message="锁定楼梯核几何被改动",
                            hard=True,
                            source="system",
                        )
                    )
                    break

    locked_room_ids = locks.locked_room_ids
    for lz in locks.zones:
        z_kind = lz.zone.value if hasattr(lz.zone, "value") else str(lz.zone)
        match = None
        if lz.zone_id:
            match = next(
                (z for z in candidate.zone_placements if z.id == lz.zone_id),
                None,
            )
            if match is None:
                violations.append(
                    Violation(
                        constraint_id="lock.zone_breached",
                        room_ids=list(lz.room_ids),
                        message=(
                            f"锁定分区组件缺失：{lz.zone_id}"
                        ),
                        hard=True,
                        source="system",
                    )
                )
                continue
            if not _same_rect(
                match.rect.x, match.rect.y, match.rect.width, match.rect.depth, lz
            ):
                violations.append(
                    Violation(
                        constraint_id="lock.zone_breached",
                        room_ids=list(lz.room_ids),
                        message=(
                            f"锁定分区 envelope 被改动：{lz.zone_id}"
                        ),
                        hard=True,
                        source="system",
                    )
                )
                continue
        else:
            match = next(
                (
                    z
                    for z in candidate.zone_placements
                    if z.resolved_kind() == z_kind
                    and z.floor_id == lz.floor_id
                    and abs(z.rect.x - lz.x) <= _TOL
                    and abs(z.rect.y - lz.y) <= _TOL
                    and abs(z.rect.width - lz.width) <= _TOL
                    and abs(z.rect.depth - lz.depth) <= _TOL
                ),
                None,
            )
            if match is None:
                same_kind = [
                    z
                    for z in candidate.zone_placements
                    if z.resolved_kind() == z_kind and z.floor_id == lz.floor_id
                ]
                if not same_kind or not any(
                    _same_rect(z.rect.x, z.rect.y, z.rect.width, z.rect.depth, lz)
                    for z in same_kind
                ):
                    violations.append(
                        Violation(
                            constraint_id="lock.zone_breached",
                            room_ids=list(lz.room_ids),
                            message=(
                                f"锁定分区 envelope 被改动：{z_kind} @ {lz.floor_id}"
                            ),
                            hard=True,
                            source="system",
                        )
                    )
                    continue

        envelope = Rect(x=lz.x, y=lz.y, width=lz.width, depth=lz.depth)
        for rid in lz.room_ids:
            if rid in locked_room_ids:
                continue
            p = placement_by_id.get(rid)
            if p is None:
                continue
            pr = Rect(
                x=p.rect.x, y=p.rect.y, width=p.rect.width, depth=p.rect.depth
            )
            if not _contains_tol(envelope, pr):
                label = lz.zone_id or f"{z_kind}@{lz.floor_id}"
                violations.append(
                    Violation(
                        constraint_id="lock.zone_breached",
                        room_ids=[rid],
                        message=(
                            f"分区锁成员越界：{rid} 不在 {label} envelope 内"
                        ),
                        hard=True,
                        source="system",
                    )
                )

    return ConstraintEvaluationResult.from_violations(violations)


def _same_rect(x: float, y: float, w: float, d: float, lock) -> bool:
    return (
        abs(x - lock.x) <= _TOL
        and abs(y - lock.y) <= _TOL
        and abs(w - lock.width) <= _TOL
        and abs(d - lock.depth) <= _TOL
    )


def _contains_tol(outer: Rect, inner: Rect, tol: float = _TOL) -> bool:
    return (
        inner.x >= outer.x - tol
        and inner.y >= outer.y - tol
        and inner.x + inner.width <= outer.x + outer.width + tol
        and inner.y + inner.depth <= outer.y + outer.depth + tol
    )

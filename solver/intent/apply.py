"""将 DesignIntentPatch 应用到 DesignProgram，并推导 RegenerationScope。"""

from __future__ import annotations

from uuid import uuid4

from packages.schema.constraints import (
    AdjacencyConstraint,
    ConstraintSource,
    OrientationConstraint,
    SeparationConstraint,
)
from packages.schema.intent_patch import (
    DesignIntentPatch,
    IntentChangeAction,
    IntentPatchPreview,
    IntentPriority,
    IntentRegenerationMode,
)
from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.regeneration import RegenerationScope
from packages.schema.site import CardinalOrientation

from solver.semantics.roles import (
    is_kitchen,
    is_living,
    is_master_bedroom,
)


def _is_bedroom_like(room) -> bool:
    if is_master_bedroom(room):
        return True
    cat = (room.category or "").lower()
    if cat == "private" and "卫" not in (room.name or ""):
        return True
    return "卧" in (room.name or "")


def _role_match(room, role: str) -> bool:
    key = role.lower().replace("-", "_").replace(" ", "_")
    if room.id == role or room.id == key:
        return True
    if key in ("living", "living_room") and is_living(room):
        return True
    if key in ("kitchen",) and is_kitchen(room):
        return True
    if key in ("master", "master_bedroom", "primary_bedroom") and is_master_bedroom(room):
        return True
    if key in ("bedroom", "bed") and _is_bedroom_like(room):
        return True
    name = (room.name or "").lower()
    return key in name or role in (room.name or "")


def resolve_room_ids(program: DesignProgram, token: str | None) -> list[str]:
    if not token:
        return []
    hits = [r.id for r in program.rooms if _role_match(r, token)]
    if hits:
        return hits
    # 直接 id
    if any(r.id == token for r in program.rooms):
        return [token]
    return []


def _area_factor(action: IntentChangeAction, value: float | None) -> float:
    delta = float(value) if value is not None else 0.15
    delta = max(0.05, min(0.5, abs(delta)))
    if action == IntentChangeAction.INCREASE_TARGET_AREA:
        return 1.0 + delta
    return max(0.5, 1.0 - delta)


def apply_intent_patch(
    program: DesignProgram,
    patch: DesignIntentPatch,
    *,
    candidate: LayoutCandidate | None = None,
) -> tuple[DesignProgram, RegenerationScope, IntentPatchPreview]:
    """
    返回 (新 program, scope, preview)。

    不修改几何；局部/全量 regen 由调用方执行。
    """
    new_program = program.model_copy(deep=True)
    deltas: list[str] = []
    warnings: list[str] = []
    touched: set[str] = set()

    locked: list[str] = []
    for token in patch.preserve:
        ids = resolve_room_ids(new_program, token)
        if not ids:
            warnings.append(f"无法解析 preserve：{token}")
            continue
        locked.extend(ids)
        deltas.append(f"锁定 {', '.join(ids)}")
    locked = sorted(set(locked))

    for ch in patch.changes:
        targets = resolve_room_ids(new_program, ch.target)
        partners = resolve_room_ids(new_program, ch.partner)

        if ch.action in (
            IntentChangeAction.INCREASE_TARGET_AREA,
            IntentChangeAction.DECREASE_TARGET_AREA,
        ):
            if not targets:
                warnings.append(f"面积调整目标未解析：{ch.target}")
                continue
            factor = _area_factor(ch.action, float(ch.value) if ch.value is not None else None)
            rooms = []
            for r in new_program.rooms:
                if r.id in targets:
                    old = r.target_area
                    r = r.model_copy(update={"target_area": round(old * factor, 2)})
                    deltas.append(f"{r.id} 目标面积 {old:.1f}→{r.target_area:.1f}")
                    touched.add(r.id)
                rooms.append(r)
            new_program = new_program.model_copy(update={"rooms": rooms})

        elif ch.action == IntentChangeAction.SET_ORIENTATION_PREFERENCE:
            if not targets:
                warnings.append(f"朝向目标未解析：{ch.target}")
                continue
            orient = str(ch.value or "south").lower()
            try:
                CardinalOrientation(orient)
            except ValueError:
                warnings.append(f"非法朝向：{orient}")
                continue
            hard = ch.priority == IntentPriority.REQUIRED
            constraints = list(new_program.constraints)
            for rid in targets:
                constraints.append(
                    OrientationConstraint(
                        id=f"intent-orient-{rid}-{uuid4().hex[:6]}",
                        room_id=rid,
                        preferred_orientation=orient,
                        hard=hard,
                        weight=1.0 if hard else 0.8,
                        source=ConstraintSource.USER,
                        source_key="intent_patch.set_orientation",
                        description=f"IntentPatch 朝向偏好 {orient}",
                    )
                )
                deltas.append(f"{rid} 朝向偏好 {orient}")
                touched.add(rid)
            new_program = new_program.model_copy(update={"constraints": constraints})

        elif ch.action == IntentChangeAction.REQUIRE_ADJACENCY:
            if not targets or not partners:
                warnings.append("require_adjacency 需要 target 与 partner")
                continue
            constraints = list(new_program.constraints)
            for a in targets:
                for b in partners:
                    if a == b:
                        continue
                    constraints.append(
                        AdjacencyConstraint(
                            id=f"intent-adj-{a}-{b}-{uuid4().hex[:6]}",
                            room_a_id=a,
                            room_b_id=b,
                            hard=ch.priority == IntentPriority.REQUIRED,
                            weight=1.0,
                            source=ConstraintSource.USER,
                            source_key="intent_patch.require_adjacency",
                            description="IntentPatch 邻接要求",
                        )
                    )
                    deltas.append(f"要求邻接 {a}↔{b}")
                    touched.update((a, b))
            new_program = new_program.model_copy(update={"constraints": constraints})

        elif ch.action == IntentChangeAction.AVOID_ADJACENCY:
            if not targets or not partners:
                warnings.append("avoid_adjacency 需要 target 与 partner")
                continue
            constraints = list(new_program.constraints)
            for a in targets:
                for b in partners:
                    if a == b:
                        continue
                    constraints.append(
                        SeparationConstraint(
                            id=f"intent-sep-{a}-{b}-{uuid4().hex[:6]}",
                            room_a_id=a,
                            room_b_id=b,
                            hard=ch.priority == IntentPriority.REQUIRED,
                            weight=1.0,
                            source=ConstraintSource.USER,
                            source_key="intent_patch.avoid_adjacency",
                            description="IntentPatch 分离要求",
                        )
                    )
                    deltas.append(f"避免邻接 {a}↔{b}")
                    touched.update((a, b))
            new_program = new_program.model_copy(update={"constraints": constraints})

        elif ch.action == IntentChangeAction.AVOID_PRIVATE_THROUGH:
            # Gate 已有 private_through 评价；标卧室为 touched 促局部 regen
            deltas.append("优先消除穿卧室通行（avoid_private_through）")
            for r in new_program.rooms:
                if _is_bedroom_like(r):
                    touched.add(r.id)

        elif ch.action == IntentChangeAction.REDUCE_CORRIDOR_PREFERENCE:
            deltas.append("降低走廊偏好（软目标）")
            for r in new_program.rooms:
                if (r.category or "").lower() == "circulation":
                    touched.add(r.id)

    program_ids = {r.id for r in new_program.rooms}
    locked = [rid for rid in locked if rid in program_ids]
    if patch.regeneration == IntentRegenerationMode.FULL and locked:
        warnings.append("full regen 与 preserve 同时存在：将改为 partial 并锁定 preserve")

    if patch.regeneration == IntentRegenerationMode.FULL and not locked:
        mutable = sorted(program_ids)
    else:
        mutable = sorted((touched | set()) - set(locked)) or sorted(
            program_ids - set(locked)
        )
        if not mutable:
            # 至少动一个非锁定房间
            mutable = sorted(program_ids - set(locked))[:1] or sorted(program_ids)[:1]
            warnings.append("无明确变更目标：默认重排一个未锁定房间")

    # locked_rooms 为空 → 默认锁定「全部 − mutable」，避免只钉 preserve 导致其余房间全放开
    scope = RegenerationScope(
        mutable_rooms=mutable,
        locked_rooms=[],
        preserve_topology=True,
        preserve_floor_assignment=True,
    )
    effective_locked = sorted(program_ids - set(mutable))

    preview = IntentPatchPreview(
        patch=patch,
        locked_rooms=effective_locked,
        mutable_rooms=mutable,
        program_deltas=deltas,
        warnings=warnings,
        ok=len(warnings) == 0 or bool(deltas),
    )
    _ = candidate  # 预留：基于当前几何推断更精确 mutable 邻域
    return new_program, scope, preview

"""IntentPatch 应用后将变更写回 RequirementSpec（需求事实源）。"""

from __future__ import annotations

from packages.schema.intent_patch import DesignIntentPatch, IntentChangeAction
from packages.schema.program import DesignProgram
from packages.schema.requirements import RelationIntent, RequirementSpec
from packages.schema.site import CardinalOrientation

from solver.intent.apply import resolve_room_ids


def _space_matches_room(space_id: str | None, space_name: str, room_id: str, room_name: str | None) -> bool:
    if space_id and space_id == room_id:
        return True
    if space_name and room_name and space_name == room_name:
        return True
    return False


def sync_requirement_spec_after_intent(
    spec: RequirementSpec,
    patched_program: DesignProgram,
    patch: DesignIntentPatch,
) -> RequirementSpec:
    """
    将 IntentPatch 对 DesignProgram 的修改镜像到 RequirementSpec。

    - 目标面积 / 朝向：按房间 id/name 写回 spaces
    - 邻接/分离：追加 relation_intents
    - 缩短走廊：preferences.prefer_short_corridor = True
    """
    rooms_by_id = {r.id: r for r in patched_program.rooms}
    spaces = []
    for space in spec.spaces:
        updates: dict = {}
        matched = None
        if space.id and space.id in rooms_by_id:
            matched = rooms_by_id[space.id]
        else:
            for r in patched_program.rooms:
                if _space_matches_room(space.id, space.name, r.id, r.name):
                    matched = r
                    break
        if matched is not None:
            updates["target_area"] = matched.target_area
            if space.id is None:
                updates["id"] = matched.id
        spaces.append(space.model_copy(update=updates) if updates else space)

    # 朝向：直接来自 patch（Program 侧写入 OrientationConstraint，不改 RoomSpec）
    for ch in patch.changes:
        if ch.action != IntentChangeAction.SET_ORIENTATION_PREFERENCE:
            continue
        orient_raw = str(ch.value or "south").lower()
        try:
            orient = CardinalOrientation(orient_raw)
        except ValueError:
            continue
        targets = set(resolve_room_ids(patched_program, ch.target))
        spaces = [
            (
                s.model_copy(update={"preferred_orientation": orient})
                if (s.id in targets)
                or any(
                    _space_matches_room(s.id, s.name, rid, rooms_by_id[rid].name)
                    for rid in targets
                    if rid in rooms_by_id
                )
                else s
            )
            for s in spaces
        ]

    relations = list(spec.relation_intents)
    for ch in patch.changes:
        if ch.action not in (
            IntentChangeAction.REQUIRE_ADJACENCY,
            IntentChangeAction.AVOID_ADJACENCY,
        ):
            continue
        targets = resolve_room_ids(patched_program, ch.target)
        partners = resolve_room_ids(patched_program, ch.partner)
        kind = (
            "adjacency"
            if ch.action == IntentChangeAction.REQUIRE_ADJACENCY
            else "separation"
        )
        strength = "required" if ch.priority.value == "required" else "preferred"
        for a in targets:
            for b in partners:
                if a == b:
                    continue
                name_a = rooms_by_id[a].name or a if a in rooms_by_id else a
                name_b = rooms_by_id[b].name or b if b in rooms_by_id else b
                relations.append(
                    RelationIntent(
                        a=name_a,
                        b=name_b,
                        kind=kind,  # type: ignore[arg-type]
                        strength=strength,  # type: ignore[arg-type]
                        note="intent_patch",
                    )
                )

    prefs = spec.preferences
    if any(
        c.action == IntentChangeAction.REDUCE_CORRIDOR_PREFERENCE for c in patch.changes
    ):
        prefs = prefs.model_copy(update={"prefer_short_corridor": True})

    return spec.model_copy(
        update={
            "spaces": spaces,
            "relation_intents": relations,
            "preferences": prefs,
        }
    )

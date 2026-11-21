"""IntentPatch 应用后将变更写回 RequirementSpec（需求事实源）。"""

from __future__ import annotations

from packages.schema.intent_patch import DesignIntentPatch, IntentChangeAction
from packages.schema.program import DesignProgram
from packages.schema.requirements import RelationIntent, RequirementSpec, SpaceRequirement
from packages.schema.site import CardinalOrientation

from solver.intent.apply import resolve_room_ids


def _match_spaces_to_rooms(
    spaces: list[SpaceRequirement],
    program: DesignProgram,
) -> list[tuple[SpaceRequirement, str | None]]:
    """
    一对一匹配 space → room_id。

    优先 id；无 id 时按名称消费尚未占用的房间，禁止把同名多间全部归并到同一 room_id。
    """
    used: set[str] = set()
    out: list[tuple[SpaceRequirement, str | None]] = []
    rooms_by_id = {r.id: r for r in program.rooms}

    for space in spaces:
        if space.id and space.id in rooms_by_id and space.id not in used:
            used.add(space.id)
            out.append((space, space.id))
            continue
        matched_id: str | None = None
        if space.name:
            for r in program.rooms:
                if r.id in used:
                    continue
                if (r.name or "") == space.name:
                    matched_id = r.id
                    used.add(r.id)
                    break
        out.append((space, matched_id))
    return out


def sync_requirement_spec_after_intent(
    spec: RequirementSpec,
    patched_program: DesignProgram,
    patch: DesignIntentPatch,
) -> RequirementSpec:
    """
    将 IntentPatch 对 DesignProgram 的修改镜像到 RequirementSpec。

    - 目标面积 / 朝向：按稳定一对一映射写回 spaces
    - 邻接/分离：追加 relation_intents（优先存 room id）
    - 缩短走廊：preferences.prefer_short_corridor = True
    """
    rooms_by_id = {r.id: r for r in patched_program.rooms}
    matched = _match_spaces_to_rooms(spec.spaces, patched_program)
    spaces: list[SpaceRequirement] = []
    for space, room_id in matched:
        updates: dict = {}
        if room_id and room_id in rooms_by_id:
            room = rooms_by_id[room_id]
            updates["target_area"] = room.target_area
            if space.id is None:
                updates["id"] = room.id
        spaces.append(space.model_copy(update=updates) if updates else space)

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
                if s.id in targets
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
                # 存 room id，便于 normalize 稳定回编译（名称可重复）
                relations.append(
                    RelationIntent(
                        a=a,
                        b=b,
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

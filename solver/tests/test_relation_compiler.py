"""relation_intents 保存 → normalize → 约束仍在。"""

from __future__ import annotations

from packages.schema.requirements import (
    RelationIntent,
    RequirementSpec,
    SiteRequirements,
    SpaceRequirement,
)
from solver.program.requirements_normalize import normalize_requirements_to_program


def test_adjacency_relation_survives_renormalize():
    req = RequirementSpec(
        site=SiteRequirements(width=11, depth=13),
        floor_count=1,
        spaces=[
            SpaceRequirement(id="kitchen", name="厨房", category="wet", target_area=12),
            SpaceRequirement(id="dining", name="餐厅", category="public", target_area=10),
            SpaceRequirement(id="living", name="客厅", category="public", target_area=24),
        ],
        relation_intents=[
            RelationIntent(
                a="kitchen",
                b="dining",
                kind="adjacency",
                strength="required",
                note="must",
            ),
            RelationIntent(
                a="living",
                b="kitchen",
                kind="separation",
                strength="preferred",
            ),
            RelationIntent(
                a="dining",
                b="living",
                kind="open_connection",
                strength="required",
            ),
        ],
    )
    program = normalize_requirements_to_program(req)
    adj = [
        c
        for c in program.constraints
        if getattr(c, "kind", None) and c.kind.value == "adjacency"
        and {c.room_a_id, c.room_b_id} == {"kitchen", "dining"}
    ]
    assert adj, program.constraints
    sep = [
        c
        for c in program.constraints
        if getattr(c, "kind", None) and c.kind.value == "separation"
        and {c.room_a_id, c.room_b_id} == {"living", "kitchen"}
    ]
    assert sep
    assert program.access_graph is not None
    opens = [
        c
        for c in program.access_graph.connections
        if c.type.value == "open" and {c.a, c.b} == {"dining", "living"}
    ]
    assert opens


def test_spec_sync_duplicate_bedroom_names_keep_distinct_ids():
    from packages.schema.intent_patch import (
        DesignIntentPatch,
        IntentChange,
        IntentChangeAction,
    )
    from packages.schema.program import DesignProgram
    from packages.schema.room import RoomCategory, RoomSpec
    from packages.schema.site import Rect2D, SiteSpec
    from solver.intent.spec_sync import sync_requirement_spec_after_intent

    spec = RequirementSpec(
        site=SiteRequirements(width=11, depth=13),
        spaces=[
            SpaceRequirement(name="卧室", category="private", target_area=12),
            SpaceRequirement(name="卧室", category="private", target_area=12),
        ],
    )
    program = DesignProgram(
        project_id="t",
        site=SiteSpec(width=11, depth=13),
        buildable=Rect2D(x=0, y=0, width=11, depth=13),
        floors=[],
        rooms=[
            RoomSpec(id="r1", name="卧室", category=RoomCategory.PRIVATE, target_area=13.8),
            RoomSpec(id="r2", name="卧室", category=RoomCategory.PRIVATE, target_area=13.8),
        ],
        constraints=[],
    )
    patch = DesignIntentPatch(
        changes=[
            IntentChange(
                action=IntentChangeAction.INCREASE_TARGET_AREA,
                target="bedroom",
                value=0.15,
            )
        ]
    )
    synced = sync_requirement_spec_after_intent(spec, program, patch)
    ids = [s.id for s in synced.spaces]
    assert ids == ["r1", "r2"]

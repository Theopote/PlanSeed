"""DesignIntentPatch 确定性解析与应用。"""

from __future__ import annotations

from packages.llm.intent_parser import parse_intent_patch_deterministic
from packages.schema.intent_patch import IntentChangeAction
from solver.fixtures.benchmark import benchmark_program
from solver.intent.apply import apply_intent_patch


def test_deterministic_parse_preserve_and_area():
    text = "我比较喜欢现在的客厅和厨房，保持它们不变。希望主卧更大一点，次卧不要通过主卧进入，同时尽量缩短走廊。"
    patch = parse_intent_patch_deterministic(text)
    assert "living" in patch.preserve or "kitchen" in patch.preserve
    actions = {c.action for c in patch.changes}
    assert IntentChangeAction.INCREASE_TARGET_AREA in actions
    assert IntentChangeAction.AVOID_PRIVATE_THROUGH in actions
    assert IntentChangeAction.REDUCE_CORRIDOR_PREFERENCE in actions


def test_apply_intent_patch_builds_scope():
    program = benchmark_program()
    patch = parse_intent_patch_deterministic(
        "保持客厅不变。希望主卧大一点。"
    )
    new_prog, scope, preview = apply_intent_patch(program, patch)
    assert preview.mutable_rooms
    assert "r1" in scope.locked_rooms or any(
        r in scope.locked_rooms for r in preview.locked_rooms
    )
    assert scope.preserve_topology is True
    # 面积可能变化
    assert new_prog.rooms

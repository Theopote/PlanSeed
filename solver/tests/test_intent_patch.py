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
    assert any(
        c.target == "master_bedroom"
        for c in patch.changes
        if c.action.value == "increase_target_area"
    )
    new_prog, scope, preview = apply_intent_patch(program, patch)
    assert preview.mutable_rooms
    # 默认锁定补集：客厅保留且不在 mutable
    assert "r1" not in scope.mutable_rooms
    assert "r1" in preview.locked_rooms
    assert scope.locked_rooms == []  # 由 solver 推补集
    assert scope.preserve_topology is True
    assert new_prog.rooms


def test_apply_intent_partial_regen_keeps_valids():
    from solver.generators.guillotine import GuillotineGenerator
    from solver.pipeline import run_pipeline
    from solver.regeneration.scope import locks_from_regeneration_scope

    program = benchmark_program()
    base = GuillotineGenerator().generate(program, seed=0)
    patch = parse_intent_patch_deterministic("保持客厅不变，主卧大一点")
    patched, scope, _preview = apply_intent_patch(program, patch, candidate=base)
    locks = locks_from_regeneration_scope(scope, patched, base)
    cfg = patched.solver_config.model_copy(
        update={"candidate_count": 8, "return_top_k": 3, "base_seed": 10}
    )
    patched = patched.model_copy(update={"solver_config": cfg})
    result = run_pipeline(patched, locks=locks, generator=GuillotineGenerator())
    assert result.valid >= 1, result.violation_summary


def test_secondary_bedroom_does_not_resize_master():
    program = benchmark_program()
    patch = parse_intent_patch_deterministic("次卧大一点")
    assert any(
        c.target == "secondary_bedroom"
        for c in patch.changes
        if c.action == IntentChangeAction.INCREASE_TARGET_AREA
    )
    new_prog, _scope, preview = apply_intent_patch(program, patch)
    by_id = {r.id: r.target_area for r in new_prog.rooms}
    old = {r.id: r.target_area for r in program.rooms}
    # 主卧 r5 面积不变；至少一间次卧变大
    assert by_id["r5"] == old["r5"]
    grew = [rid for rid in ("r7", "r8") if by_id[rid] > old[rid]]
    assert grew, preview.program_deltas


def test_reduce_corridor_raises_penalty():
    program = benchmark_program()
    patch = parse_intent_patch_deterministic("尽量缩短走廊")
    new_prog, _scope, _preview = apply_intent_patch(program, patch)
    assert new_prog.solver_config.corridor_penalty >= 1.2
    assert new_prog.solver_config.score_weight_overrides.get("circulation", 0) >= 0.22


def test_increase_area_syncs_area_bound_constraint():
    from packages.schema.constraints import AreaConstraint, ConstraintKind
    from packages.schema.intent_patch import DesignIntentPatch, IntentChange

    program = benchmark_program()
    master = next(r for r in program.rooms if r.id == "r5")
    old_target = master.target_area
    old_bound = next(
        c
        for c in program.constraints
        if c.kind == ConstraintKind.AREA
        and isinstance(c, AreaConstraint)
        and c.room_id == "r5"
    )
    patch = DesignIntentPatch(
        changes=[
            IntentChange(
                action=IntentChangeAction.INCREASE_TARGET_AREA,
                target="master_bedroom",
                value=0.2,
            )
        ]
    )
    new_prog, _scope, _preview = apply_intent_patch(program, patch)
    new_master = next(r for r in new_prog.rooms if r.id == "r5")
    assert new_master.target_area > old_target
    new_bound = next(
        c
        for c in new_prog.constraints
        if c.kind == ConstraintKind.AREA
        and isinstance(c, AreaConstraint)
        and c.room_id == "r5"
    )
    assert new_bound.target_area == new_master.target_area
    assert new_bound.min_area == new_master.resolved_min_area()
    assert new_bound.max_area == new_master.resolved_max_area()
    assert new_bound.min_area != old_bound.min_area or new_bound.target_area != old_bound.target_area

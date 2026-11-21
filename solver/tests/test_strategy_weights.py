"""TopologyStrategy 权重进入 SolverConfig / 评价。"""

from __future__ import annotations

from packages.schema.requirement_fingerprint import requirement_revision_id
from packages.schema.requirements import RequirementSpec, SiteRequirements, SpaceRequirement
from solver.evaluation.strategy_weights import score_weights_from_config
from solver.fixtures.benchmark import benchmark_program, benchmark_requirement_spec
from solver.topology.strategy import apply_topology_strategy


def test_daylight_strategy_applies_weights_without_edges():
    program = benchmark_program()
    patched = apply_topology_strategy(program, "daylight_courtyard")
    assert patched.solver_config.score_weight_overrides.get("environment") == 1.25
    assert patched.solver_config.corridor_penalty == 0.85
    w = score_weights_from_config(patched.solver_config)
    # 默认 circulation * 0.85
    assert w.environment == 1.25
    assert abs(w.circulation - 0.16 * 0.85) < 1e-6


def test_requirement_revision_changes_with_area():
    a = benchmark_requirement_spec()
    b = a.model_copy(
        update={
            "spaces": [
                s.model_copy(update={"target_area": (s.target_area or 10) + 5})
                if s.id == "r5"
                else s
                for s in a.spaces
            ]
        }
    )
    assert requirement_revision_id(a) != requirement_revision_id(b)
    assert requirement_revision_id(a) == requirement_revision_id(
        RequirementSpec.model_validate(a.model_dump())
    )


def test_fingerprint_stable_for_same_spec():
    spec = RequirementSpec(
        site=SiteRequirements(width=12, depth=15),
        spaces=[SpaceRequirement(id="a", name="客厅", target_area=24)],
    )
    assert requirement_revision_id(spec) == requirement_revision_id(spec.model_dump())

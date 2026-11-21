"""B12 Architectural Gate 回归 — 客卫开向与门槛通过率。"""

from __future__ import annotations

from collections import Counter

from solver.evaluation.architectural_gate import evaluate_architectural_gate
from solver.fixtures.design_suite_v2 import load_suite_case
from solver.pipeline import run_pipeline


def test_b12_guest_bath_blocker_cleared_at_n16() -> None:
    """规则3 + 客卫补开向后，B12 不应再出现 guest_bath_via_private。"""
    program = load_suite_case("B12").program
    program.solver_config.candidate_count = 16
    program.solver_config.return_top_k = 5
    program.solver_config.base_seed = 42
    result = run_pipeline(program)
    valid = [c for c in result.all_candidates if c.validation and c.validation.valid]
    assert valid, "B12 应有 valid 候选"
    codes: Counter[str] = Counter()
    passed = 0
    for c in valid:
        gate = evaluate_architectural_gate(program, c)
        if gate.passed:
            passed += 1
        for b in gate.blockers:
            codes[b.code] += 1
    assert codes.get("guest_bath_via_private", 0) == 0, codes
    # 门洞修复后绝大多数 valid 过门槛；剩余 bedroom_chain 为几何包夹
    assert passed >= 10, f"gate_pass={passed}/{len(valid)} codes={codes}"
    assert all(
        c.metrics.get("architectural_gate_pass") for c in result.top_candidates
    )

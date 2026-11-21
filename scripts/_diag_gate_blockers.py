"""诊断 Design Suite 四案例的 Architectural Gate blocker 分布。"""

from __future__ import annotations

from collections import Counter

from solver.evaluation.architectural_gate import evaluate_architectural_gate
from solver.fixtures.design_suite_v2 import load_suite_case
from solver.pipeline import run_pipeline


def main() -> None:
    cases = ["B01", "B04", "B06", "B12"]
    for cid in cases:
        program = load_suite_case(cid).program
        program.solver_config.candidate_count = 16
        program.solver_config.return_top_k = 5
        program.solver_config.base_seed = 42
        result = run_pipeline(program)
        valid = [c for c in result.all_candidates if c.validation and c.validation.valid]
        codes: Counter[str] = Counter()
        passed = 0
        for c in valid:
            gate = evaluate_architectural_gate(program, c)
            if gate.passed:
                passed += 1
            for b in gate.blockers:
                codes[b.code] += 1
            for w in gate.warnings:
                codes[f"warn:{w.code}"] += 1
        top_pass = sum(
            1
            for c in result.top_candidates
            if c.metrics.get("architectural_gate_pass")
        )
        print(
            f"{cid}: gen={result.generated} valid={result.valid} "
            f"gate_pass={passed}/{len(valid)} top_gate={top_pass}/{len(result.top_candidates)}"
        )
        for code, n in codes.most_common(12):
            print(f"  {code}: {n}")


if __name__ == "__main__":
    main()

"""多候选生成流水线。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.schema.layout import LayoutCandidate
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram

from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.evaluation.score import CompositeEvaluator
from solver.generators.guillotine import GuillotineGenerator
from solver.optimization.rank import rank_candidates


@dataclass
class PipelineMetrics:
    valid_ratio: float
    distinct_layout_count: int
    average_score: float
    top_score: float
    average_soft_violation_count: float


@dataclass
class PipelineResult:
    generated: int
    valid: int
    rejected: int
    all_candidates: list[LayoutCandidate] = field(default_factory=list)
    top_candidates: list[LayoutCandidate] = field(default_factory=list)
    violation_summary: dict[str, int] = field(default_factory=dict)

    def compute_metrics(self) -> PipelineMetrics:
        import json

        fingerprints = {
            json.dumps(
                c.model_dump(
                    exclude={"score", "metrics", "validation", "evaluation"}
                ),
                sort_keys=True,
                default=str,
            )
            for c in self.all_candidates
        }
        scored = [c.score for c in self.all_candidates if c.score is not None]
        soft_counts = [
            len(c.validation.soft_violations)
            for c in self.all_candidates
            if c.validation is not None
        ]
        return PipelineMetrics(
            valid_ratio=(self.valid / self.generated) if self.generated else 0.0,
            distinct_layout_count=len(fingerprints),
            average_score=(sum(scored) / len(scored)) if scored else 0.0,
            top_score=max(scored) if scored else 0.0,
            average_soft_violation_count=(
                sum(soft_counts) / len(soft_counts) if soft_counts else 0.0
            ),
        )


def run_pipeline(
    program: DesignProgram,
    locks: LayoutLocks | None = None,
) -> PipelineResult:
    from solver.constraints.checker import ConstraintEvaluationResult
    from solver.locks import assert_valid_layout_locks, check_lock_invariants

    generator = GuillotineGenerator()
    checker = DefaultConstraintChecker()
    evaluator = CompositeEvaluator()

    locks = locks or LayoutLocks()
    has_locks = bool(locks.rooms or locks.stair or locks.zones)
    if has_locks:
        assert_valid_layout_locks(program, locks)

    cfg = program.solver_config
    candidates: list[LayoutCandidate] = []
    violation_counts: dict[str, int] = {}

    for i in range(cfg.candidate_count):
        seed = cfg.base_seed + i
        candidate = generator.generate(program, seed, locks=locks)
        validation = checker.check(program, candidate)
        if has_locks:
            inv = check_lock_invariants(candidate, locks)
            candidate.metrics["lock_invariant_ok"] = not bool(inv.hard_violations)
            if inv.hard_violations or inv.soft_violations or inv.warnings:
                merged = ConstraintEvaluationResult(
                    hard_violations=list(validation.hard_violations),
                    soft_violations=list(validation.soft_violations),
                    warnings=list(validation.warnings),
                )
                merged.extend(inv)
                validation = merged.to_candidate_validation()
        else:
            candidate.metrics["lock_invariant_ok"] = True
        candidate.validation = validation

        if candidate.validation.valid:
            evaluation = evaluator.evaluate(program, candidate)
            candidate.evaluation = evaluation
            candidate.score = evaluation.total_score
        else:
            for v in candidate.validation.hard_violations:
                key = v.constraint_id.split(".")[0]
                if "." in v.constraint_id:
                    key = v.constraint_id
                violation_counts[key] = violation_counts.get(key, 0) + 1

        candidates.append(candidate)

    top = rank_candidates(
        candidates,
        top_k=cfg.return_top_k,
        min_diversity_threshold=cfg.min_diversity_threshold,
        buildable_width=program.buildable.width,
        buildable_depth=program.buildable.depth,
    )
    valid = sum(1 for c in candidates if c.validation and c.validation.valid)

    return PipelineResult(
        generated=len(candidates),
        valid=valid,
        rejected=len(candidates) - valid,
        all_candidates=candidates,
        top_candidates=top,
        violation_summary=violation_counts,
    )

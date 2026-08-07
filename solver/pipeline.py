"""多候选生成流水线。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.scoring import DesignScore
from solver.constraints.checker_impl import DefaultConstraintChecker
from solver.evaluation.score import CompositeEvaluator
from solver.generators.guillotine import GuillotineGenerator
from solver.optimization.rank import rank_candidates


@dataclass
class PipelineResult:
    generated: int
    valid: int
    rejected: int
    all_candidates: list[LayoutCandidate] = field(default_factory=list)
    top_candidates: list[LayoutCandidate] = field(default_factory=list)
    violation_summary: dict[str, int] = field(default_factory=dict)


def run_pipeline(program: DesignProgram) -> PipelineResult:
    generator = GuillotineGenerator()
    checker = DefaultConstraintChecker()
    evaluator = CompositeEvaluator()

    cfg = program.solver_config
    candidates: list[LayoutCandidate] = []
    violation_counts: dict[str, int] = {}

    for i in range(cfg.candidate_count):
        seed = cfg.base_seed + i
        candidate = generator.generate(program, seed)
        candidate.validation = checker.check(program, candidate)

        if candidate.validation.valid:
            score = evaluator.evaluate(program, candidate)
            candidate.score = score.total_score
        else:
            for v in candidate.validation.hard_violations:
                key = v.constraint_id.split(".")[0]
                if "." in v.constraint_id:
                    key = v.constraint_id
                violation_counts[key] = violation_counts.get(key, 0) + 1

        candidates.append(candidate)

    top = rank_candidates(candidates, top_k=cfg.return_top_k)
    valid = sum(1 for c in candidates if c.validation and c.validation.valid)

    return PipelineResult(
        generated=len(candidates),
        valid=valid,
        rejected=len(candidates) - valid,
        all_candidates=candidates,
        top_candidates=top,
        violation_summary=violation_counts,
    )

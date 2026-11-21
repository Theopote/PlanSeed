"""TopologyStrategy / Intent → ScoreWeights。"""

from __future__ import annotations

from packages.schema.program import DesignProgram, SolverConfig
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights

_AXIS_FIELDS = (
    "program",
    "spatial",
    "circulation",
    "privacy",
    "environment",
    "technical",
    "robustness",
)


def score_weights_from_config(cfg: SolverConfig) -> ScoreWeights:
    """应用 score_weight_overrides，并用 corridor_penalty 缩放 circulation。"""
    data = DEFAULT_WEIGHTS.model_dump()
    for key, val in (cfg.score_weight_overrides or {}).items():
        if key in data and isinstance(val, (int, float)):
            data[key] = float(val)
    # corridor_penalty>1 → 更重视 circulation（惩罚差交通）；<1 放宽
    pen = float(getattr(cfg, "corridor_penalty", 1.0) or 1.0)
    data["circulation"] = float(data["circulation"]) * pen
    return ScoreWeights.model_validate(data)


def evaluator_for_program(program: DesignProgram):
    from solver.evaluation.score import CompositeEvaluator

    return CompositeEvaluator(weights=score_weights_from_config(program.solver_config))

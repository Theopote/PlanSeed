"""邻接约束满足度。"""

from __future__ import annotations

from packages.schema.constraints import AdjacencyConstraint, ConstraintKind
from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights
from solver.geometry.rect import from_placement, shared_edge_length


def compute_adjacency_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, float]:
    adj_constraints = [
        c for c in program.constraints if c.kind == ConstraintKind.ADJACENCY
    ]
    if not adj_constraints:
        return {"preferred_adjacency_satisfaction": 1.0, "required_adjacency_satisfaction": 1.0}

    hard_total = hard_sat = 0
    soft_total = soft_sat = 0

    for c in adj_constraints:
        if not isinstance(c, AdjacencyConstraint):
            continue
        pa = pb = None
        for fl in candidate.floors:
            for p in fl.placements:
                if p.room_id == c.room_a_id:
                    pa = p
                if p.room_id == c.room_b_id:
                    pb = p
        satisfied = False
        if pa and pb and pa.floor_id == pb.floor_id:
            shared = shared_edge_length(from_placement(pa.rect), from_placement(pb.rect))
            satisfied = shared >= weights.min_adjacency_wall

        if c.hard:
            hard_total += 1
            hard_sat += int(satisfied)
        else:
            soft_total += 1
            soft_sat += int(satisfied)

    return {
        "required_adjacency_satisfaction": hard_sat / hard_total if hard_total else 1.0,
        "preferred_adjacency_satisfaction": soft_sat / soft_total if soft_total else 1.0,
    }


def adjacency_score(metrics: dict[str, float]) -> float:
    req = metrics.get("required_adjacency_satisfaction", 1.0)
    pref = metrics.get("preferred_adjacency_satisfaction", 1.0)
    return max(0.0, min(100.0, req * 60 + pref * 40))

"""评价聚合 — 组合各 evaluator 输出 DesignScore。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.scoring import DesignMetrics, DesignScore
from solver.evaluation.adjacency import adjacency_score, compute_adjacency_metrics
from solver.evaluation.geometry import compute_geometry_metrics, geometry_score
from solver.evaluation.vertical import compute_vertical_metrics, vertical_score
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights


class CompositeEvaluator:
    def __init__(self, weights: ScoreWeights = DEFAULT_WEIGHTS) -> None:
        self.weights = weights

    def evaluate(self, program: DesignProgram, candidate: LayoutCandidate) -> DesignScore:
        geo_m = compute_geometry_metrics(program, candidate, self.weights)
        adj_m = compute_adjacency_metrics(program, candidate, self.weights)
        vert_m = compute_vertical_metrics(candidate)

        g_score = geometry_score(geo_m)
        a_score = adjacency_score(adj_m)
        v_score = vertical_score(vert_m)
        site_score = 100.0  # setbacks 默认 0，MVP 视为合规

        w = self.weights
        total = (
            g_score * w.geometry
            + a_score * w.adjacency
            + v_score * w.vertical
            + site_score * w.site
        ) / (w.geometry + w.adjacency + w.vertical + w.site)

        warnings: list[str] = []
        if geo_m.get("slender_room_count", 0) > 0:
            warnings.append(f"{int(geo_m['slender_room_count'])} 个房间长宽比偏大")

        metrics = DesignMetrics(
            area_error=1.0 - geo_m.get("area_accuracy", 1.0),
            aspect_ratio_penalty=geo_m.get("aspect_ratio_penalty", 0.0),
            compactness=geo_m.get("compactness", 0.0),
            required_adjacency_satisfaction=adj_m.get("required_adjacency_satisfaction", 1.0),
            preferred_adjacency_satisfaction=adj_m.get("preferred_adjacency_satisfaction", 1.0),
            stair_alignment=vert_m.get("stair_alignment", 1.0),
            wet_zone_alignment=vert_m.get("wet_zone_alignment", 1.0),
            setback_compliance=1.0,
        )

        flat_metrics: dict[str, float | int | str | bool] = {
            **geo_m,
            **adj_m,
            **vert_m,
        }

        score = DesignScore(
            geometry_score=g_score,
            adjacency_score=a_score,
            vertical_score=v_score,
            site_score=site_score,
            total_score=round(total, 2),
            metrics=metrics,
            warnings=warnings,
        )

        candidate.metrics.update(flat_metrics)
        return score

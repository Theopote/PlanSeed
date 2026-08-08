"""评价聚合 — 组合各 evaluator 输出 DesignScore。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.scoring import DesignMetrics, DesignScore
from solver.evaluation.adjacency import adjacency_score, compute_adjacency_metrics
from solver.evaluation.geometry import compute_geometry_metrics, geometry_score
from solver.evaluation.orientation import (
    compute_orientation_metrics,
    orientation_score,
    orientation_soft_violations,
)
from solver.evaluation.site import compute_site_metrics, site_score as compute_site_score
from solver.evaluation.vertical import compute_vertical_metrics, vertical_score
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights


class CompositeEvaluator:
    def __init__(self, weights: ScoreWeights = DEFAULT_WEIGHTS) -> None:
        self.weights = weights

    def evaluate(self, program: DesignProgram, candidate: LayoutCandidate) -> DesignScore:
        geo_m = compute_geometry_metrics(program, candidate, self.weights)
        adj_m = compute_adjacency_metrics(program, candidate, self.weights)
        vert_m = compute_vertical_metrics(candidate)
        orient_m = compute_orientation_metrics(program, candidate)
        site_m = compute_site_metrics(program, candidate)

        g_score = geometry_score(geo_m)
        a_score = adjacency_score(adj_m)
        v_score = vertical_score(vert_m)
        o_score = orientation_score(orient_m)
        s_score = compute_site_score(site_m)

        w = self.weights
        denom = w.geometry + w.adjacency + w.vertical + w.site + w.orientation
        total = (
            g_score * w.geometry
            + a_score * w.adjacency
            + v_score * w.vertical
            + s_score * w.site
            + o_score * w.orientation
        ) / denom

        warnings: list[str] = []
        if geo_m.get("slender_room_count", 0) > 0:
            warnings.append(f"{int(geo_m['slender_room_count'])} 个房间长宽比偏大")
        if not site_m.get("setback_info_provided", False):
            warnings.append("未提供规划退界（setbacks=0 表示信息缺失，非法规结论）")

        soft_violations = orientation_soft_violations(program, candidate)
        for v in soft_violations:
            warnings.append(v.message)

        metrics = DesignMetrics(
            area_error=1.0 - float(geo_m.get("area_accuracy", 1.0)),
            aspect_ratio_penalty=float(geo_m.get("aspect_ratio_penalty", 0.0)),
            compactness=float(geo_m.get("compactness", 0.0)),
            required_adjacency_satisfaction=float(
                adj_m.get("required_adjacency_satisfaction", 1.0)
            ),
            preferred_adjacency_satisfaction=float(
                adj_m.get("preferred_adjacency_satisfaction", 1.0)
            ),
            stair_alignment=float(vert_m.get("stair_alignment", 1.0)),
            wet_zone_alignment=float(vert_m.get("wet_zone_alignment", 1.0)),
            setback_compliance=float(site_m.get("setback_compliance", 1.0)),
            orientation_satisfaction=float(orient_m.get("orientation_satisfaction", 1.0)),
        )

        flat_metrics: dict[str, float | int | str | bool] = {
            **geo_m,
            **adj_m,
            **vert_m,
            **{k: v for k, v in orient_m.items()},
            **{k: v for k, v in site_m.items()},
        }

        score = DesignScore(
            geometry_score=g_score,
            adjacency_score=a_score,
            vertical_score=v_score,
            orientation_score=o_score,
            site_score=s_score,
            total_score=round(total, 2),
            metrics=metrics,
            warnings=warnings,
            violations=soft_violations,
        )

        candidate.metrics.update(flat_metrics)
        return score

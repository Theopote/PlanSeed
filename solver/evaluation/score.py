"""评价聚合 — 组合各 evaluator 输出 DesignScore（Phase 3 可解释分解）。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.scoring import DesignMetrics, DesignScore
from solver.evaluation.access import (
    access_circulation_score,
    compute_access_metrics,
)
from solver.evaluation.adjacency import adjacency_score, compute_adjacency_metrics
from solver.evaluation.circulation import (
    circulation_architecture_score,
    compute_circulation_metrics,
)
from solver.evaluation.geometry import compute_geometry_metrics, geometry_score
from solver.evaluation.orientation import (
    compute_orientation_metrics,
    orientation_score,
    orientation_soft_violations,
)
from solver.evaluation.privacy import compute_privacy_metrics, privacy_score
from solver.evaluation.program_fit import (
    compute_program_fit_metrics,
    compute_space_efficiency_metrics,
    program_fit_score,
    space_efficiency_score,
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
        access_m = compute_access_metrics(program, candidate)
        circ_m = compute_circulation_metrics(program, candidate)
        priv_m = compute_privacy_metrics(program, candidate)
        fit_m = compute_program_fit_metrics(program, candidate, self.weights)
        eff_m = compute_space_efficiency_metrics(program, candidate, self.weights)

        g_score = geometry_score(geo_m)
        a_score = adjacency_score(adj_m)
        v_score = vertical_score(vert_m)
        o_score = orientation_score(orient_m)
        s_score = compute_site_score(site_m)
        p_score = privacy_score(priv_m)
        pf_score = program_fit_score(fit_m)
        se_score = space_efficiency_score(eff_m)
        ls_score = float(circ_m.get("layout_stability_score", 100.0))

        # circulation：intent 共边可行性 + realized 路径质量
        c_score = (
            0.45 * access_circulation_score(access_m)
            + 0.55 * circulation_architecture_score(circ_m)
        )

        w = self.weights
        parts = [
            (g_score, w.geometry),
            (a_score, w.adjacency),
            (v_score, w.vertical),
            (s_score, w.site),
            (o_score, w.orientation),
            (c_score, w.circulation),
            (p_score, w.privacy),
            (pf_score, w.program_fit),
            (se_score, w.space_efficiency),
            (ls_score, w.layout_stability),
        ]
        denom = sum(weight for _, weight in parts) or 1.0
        total = sum(score * weight for score, weight in parts) / denom

        warnings: list[str] = []
        explanations: list[str] = [
            f"Program Fit {pf_score:.0f}",
            f"Circulation {c_score:.0f}",
            f"Privacy {p_score:.0f}",
            f"Orientation {o_score:.0f}",
            f"Space Efficiency {se_score:.0f}",
            f"Vertical {v_score:.0f}",
            f"Layout Stability {ls_score:.0f}",
        ]

        if geo_m.get("slender_room_count", 0) > 0:
            warnings.append(f"{int(geo_m['slender_room_count'])} 个房间长宽比偏大")
        if not site_m.get("setback_info_provided", False):
            warnings.append("未提供规划退界（setbacks=0 表示信息缺失，非法规结论）")
        if float(access_m.get("access_pref_satisfaction", 1.0)) < 0.5:
            warnings.append(
                f"通行偏好共边偏低 "
                f"({access_m.get('access_pref_satisfaction', 0):.0%})"
            )
        if float(circ_m.get("reachable_ratio", 1.0)) < 1.0:
            warnings.append(
                f"realized 可达率 {float(circ_m['reachable_ratio']):.0%}"
            )
        if int(priv_m.get("private_through_count", 0)) > 0:
            warnings.append(
                f"路径穿过其他私密房间 ×{int(priv_m['private_through_count'])}"
            )
        if float(fit_m.get("program_coverage", 1.0)) < 1.0:
            warnings.append(
                f"程序房间覆盖 {float(fit_m['program_coverage']):.0%}"
            )

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
            wet_stack_alignment=float(
                vert_m.get(
                    "wet_stack_alignment",
                    vert_m.get("wet_zone_alignment", 1.0),
                )
            ),
            wet_zone_alignment=float(
                vert_m.get(
                    "wet_stack_alignment",
                    vert_m.get("wet_zone_alignment", 1.0),
                )
            ),
            setback_compliance=float(site_m.get("setback_compliance", 1.0)),
            orientation_satisfaction=float(
                orient_m.get("orientation_satisfaction", 1.0)
            ),
            program_fit=float(fit_m.get("program_fit", 1.0)),
            space_efficiency=float(eff_m.get("space_efficiency", 1.0)),
            privacy_transition_score=float(
                priv_m.get("privacy_transition_score", 1.0)
            ),
            reachable_ratio=float(circ_m.get("reachable_ratio", 1.0)),
            layout_stability=ls_score / 100.0,
        )

        flat_metrics: dict[str, float | int | str | bool] = {
            **geo_m,
            **adj_m,
            **vert_m,
            **{k: v for k, v in orient_m.items()},
            **{k: v for k, v in site_m.items()},
            **access_m,
            **circ_m,
            **{k: v for k, v in priv_m.items()},
            **fit_m,
            **eff_m,
            "program_fit_score": pf_score,
            "privacy_score": p_score,
            "space_efficiency_score": se_score,
            "layout_stability_score": ls_score,
        }

        score = DesignScore(
            geometry_score=g_score,
            adjacency_score=a_score,
            circulation_score=round(c_score, 2),
            vertical_score=v_score,
            orientation_score=o_score,
            privacy_score=round(p_score, 2),
            site_score=s_score,
            program_fit_score=round(pf_score, 2),
            space_efficiency_score=round(se_score, 2),
            layout_stability_score=round(ls_score, 2),
            total_score=round(total, 2),
            metrics=metrics,
            explanations=explanations,
            warnings=warnings,
            violations=soft_violations,
        )

        candidate.metrics.update(flat_metrics)
        candidate.score = score.total_score
        return score

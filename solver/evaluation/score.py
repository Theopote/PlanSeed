"""评价聚合 — 七轴 DesignScore + DesignFinding。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.scoring import (
    DesignMetrics,
    DesignScore,
    EvaluationAxis,
    FindingSeverity,
)
from solver.evaluation.access import (
    access_circulation_score,
    compute_access_metrics,
)
from solver.evaluation.adjacency import adjacency_score, compute_adjacency_metrics
from solver.evaluation.circulation import (
    circulation_architecture_score,
    circulation_findings,
    compute_circulation_metrics,
    layout_stability_findings,
)
from solver.evaluation.findings import (
    finding,
    findings_to_explanations,
    findings_to_warnings,
)
from solver.evaluation.geometry import compute_geometry_metrics, geometry_score
from solver.evaluation.orientation import (
    compute_orientation_metrics,
    orientation_score,
    orientation_soft_violations,
)
from solver.evaluation.privacy import (
    compute_privacy_metrics,
    privacy_findings,
    privacy_score,
)
from solver.evaluation.program_fit import (
    compute_program_fit_metrics,
    compute_space_efficiency_metrics,
    program_fit_findings,
    program_fit_score,
    space_efficiency_score,
)
from solver.evaluation.site import compute_site_metrics, site_score as compute_site_score
from solver.evaluation.vertical import compute_vertical_metrics, vertical_score
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights


def _blend(a: float, b: float, share_a: float) -> float:
    share_a = min(1.0, max(0.0, share_a))
    return a * share_a + b * (1.0 - share_a)


class CompositeEvaluator:
    def __init__(self, weights: ScoreWeights = DEFAULT_WEIGHTS) -> None:
        self.weights = weights

    def evaluate(self, program: DesignProgram, candidate: LayoutCandidate) -> DesignScore:
        w = self.weights
        geo_m = compute_geometry_metrics(program, candidate, w)
        adj_m = compute_adjacency_metrics(program, candidate, w)
        vert_m = compute_vertical_metrics(candidate)
        orient_m = compute_orientation_metrics(program, candidate)
        site_m = compute_site_metrics(program, candidate)
        access_m = compute_access_metrics(program, candidate)
        circ_m = compute_circulation_metrics(program, candidate)
        priv_m = compute_privacy_metrics(program, candidate)
        fit_m = compute_program_fit_metrics(program, candidate, w)
        eff_m = compute_space_efficiency_metrics(program, candidate, w)

        # 底层切片（Metric Ownership 已去重）
        fit_s = program_fit_score(fit_m)
        adj_s = adjacency_score(adj_m)
        prop_s = geometry_score(geo_m)
        compact_s = space_efficiency_score(eff_m)
        circ_s = (
            0.45 * access_circulation_score(access_m)
            + 0.55 * circulation_architecture_score(circ_m)
        )
        priv_s = privacy_score(priv_m)
        env_s = orientation_score(orient_m)
        vert_s = vertical_score(vert_m)
        site_s = compute_site_score(site_m)
        robust_s = float(circ_m.get("layout_stability_score", 100.0))

        # 七轴
        program_s = _blend(fit_s, adj_s, w.program_fit_share)
        spatial_s = _blend(prop_s, compact_s, w.spatial_proportion_share)
        technical_s = _blend(vert_s, site_s, w.technical_vertical_share)

        parts = [
            (program_s, w.program),
            (spatial_s, w.spatial),
            (circ_s, w.circulation),
            (priv_s, w.privacy),
            (env_s, w.environment),
            (technical_s, w.technical),
            (robust_s, w.robustness),
        ]
        denom = sum(weight for _, weight in parts) or 1.0
        total = sum(score * weight for score, weight in parts) / denom

        soft_violations = orientation_soft_violations(program, candidate)

        findings = []
        findings.extend(
            circulation_findings(
                program, candidate, circ_metrics=circ_m, access_metrics=access_m
            )
        )
        findings.extend(privacy_findings(program, candidate, priv_m))
        findings.extend(
            program_fit_findings(program, candidate, fit_m, eff_m, geo_m)
        )
        findings.extend(layout_stability_findings(circ_m, candidate))

        if float(adj_m.get("required_adjacency_satisfaction", 1.0)) < 1.0:
            findings.append(
                finding(
                    id="program.adjacency_required_gap",
                    category=EvaluationAxis.PROGRAM.value,
                    severity=FindingSeverity.WARNING,
                    title="必选邻接未完全满足",
                    message=(
                        f"required adjacency "
                        f"{float(adj_m['required_adjacency_satisfaction']):.0%}"
                    ),
                    metric="required_adjacency_satisfaction",
                    measured_value=float(
                        adj_m.get("required_adjacency_satisfaction", 1.0)
                    ),
                    recommended_action="调整拓扑簇或 ConnectionResolver 共边。",
                )
            )
        elif float(adj_m.get("preferred_adjacency_satisfaction", 1.0)) >= 0.85:
            findings.append(
                finding(
                    id="program.adjacency_ok",
                    category=EvaluationAxis.PROGRAM.value,
                    severity=FindingSeverity.POSITIVE,
                    title="功能邻接较好",
                    message="偏好/必选邻接共边满足率较高。",
                    metric="preferred_adjacency_satisfaction",
                    measured_value=float(
                        adj_m.get("preferred_adjacency_satisfaction", 1.0)
                    ),
                )
            )

        if not site_m.get("setback_info_provided", False):
            findings.append(
                finding(
                    id="technical.setback_unknown",
                    category=EvaluationAxis.TECHNICAL.value,
                    severity=FindingSeverity.INFO,
                    title="未提供规划退界",
                    message="setbacks=0 表示信息缺失，不代表法规结论。",
                    metric="setback_info_provided",
                    measured_value=0.0,
                )
            )
        entry_road = float(site_m.get("entry_on_road", 1.0))
        if entry_road >= 1.0 - 1e-9 and site_m.get("setback_info_provided", False):
            pass  # 无 road 信息时默认 1.0，避免假阳性
        roads_matter = bool(program.site.road_edges)
        if roads_matter and entry_road >= 1.0 - 1e-9:
            findings.append(
                finding(
                    id="technical.entry_on_road",
                    category=EvaluationAxis.TECHNICAL.value,
                    severity=FindingSeverity.POSITIVE,
                    title="主入口临路",
                    message="ExteriorEntry 落在 road_edges 上。",
                    metric="entry_on_road",
                    measured_value=entry_road,
                )
            )
        elif roads_matter and entry_road < 0.5:
            findings.append(
                finding(
                    id="technical.entry_off_road",
                    category=EvaluationAxis.TECHNICAL.value,
                    severity=FindingSeverity.WARNING,
                    title="主入口未临路",
                    message="入口未落在声明的临路边上。",
                    metric="entry_on_road",
                    measured_value=entry_road,
                    recommended_action="调整 entrance_edge / road_edges 或入口放置。",
                )
            )

        for v in soft_violations:
            findings.append(
                finding(
                    id=f"environment.orientation:{v.constraint_id}",
                    category=EvaluationAxis.ENVIRONMENT.value,
                    severity=FindingSeverity.WARNING,
                    title="朝向偏好未满足",
                    message=v.message,
                    room_ids=list(v.room_ids),
                    recommended_action="调整房间贴边或 north_angle / preferred_orientation。",
                )
            )
        if float(orient_m.get("orientation_satisfaction", 1.0)) >= 0.99 and int(
            orient_m.get("orientation_constraint_count", 0) or 0
        ) > 0:
            findings.append(
                finding(
                    id="environment.orientation_ok",
                    category=EvaluationAxis.ENVIRONMENT.value,
                    severity=FindingSeverity.POSITIVE,
                    title="朝向偏好满足",
                    message="声明的 OrientationConstraint 均满足（世界朝向）。",
                    metric="orientation_satisfaction",
                    measured_value=float(orient_m.get("orientation_satisfaction", 1.0)),
                )
            )

        stair_al = float(vert_m.get("stair_alignment", 1.0))
        if stair_al >= 0.99 and len(candidate.floors) > 1:
            findings.append(
                finding(
                    id="technical.stair_aligned",
                    category=EvaluationAxis.TECHNICAL.value,
                    severity=FindingSeverity.POSITIVE,
                    title="楼梯跨层对齐",
                    message="楼梯核在各层位置对齐，竖向交通清晰。",
                    metric="stair_alignment",
                    measured_value=stair_al,
                )
            )
        wet_al = float(
            vert_m.get("wet_stack_alignment", vert_m.get("wet_zone_alignment", 1.0))
        )
        if wet_al >= 0.99 and len(candidate.floors) > 1:
            findings.append(
                finding(
                    id="technical.wet_aligned",
                    category=EvaluationAxis.TECHNICAL.value,
                    severity=FindingSeverity.POSITIVE,
                    title="湿区叠组对齐",
                    message="WetStack 锚跨层对齐良好。",
                    metric="wet_stack_alignment",
                    measured_value=wet_al,
                )
            )

        explanations = findings_to_explanations(findings)
        warnings = findings_to_warnings(findings)

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
            layout_stability=robust_s / 100.0,
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
            "program_score": program_s,
            "spatial_score": spatial_s,
            "circulation_score": circ_s,
            "privacy_score": priv_s,
            "environment_score": env_s,
            "technical_score": technical_s,
            "robustness_score": robust_s,
            "finding_count": len(findings),
        }

        score = DesignScore(
            program_score=round(program_s, 2),
            spatial_score=round(spatial_s, 2),
            circulation_score=round(circ_s, 2),
            privacy_score=round(priv_s, 2),
            environment_score=round(env_s, 2),
            technical_score=round(technical_s, 2),
            robustness_score=round(robust_s, 2),
            total_score=round(total, 2),
            metrics=metrics,
            findings=findings,
            explanations=explanations,
            warnings=warnings,
            violations=soft_violations,
        )

        candidate.metrics.update(flat_metrics)
        candidate.score = score.total_score
        return score

"""
Metric Ownership — 映射到七轴评价层。

原始 metric → primary EvaluationAxis；禁止同一 metric 进入多个轴的计分。

| Metric                 | Axis          |
|------------------------|---------------|
| program_coverage       | program       |
| area_accuracy          | program       |
| adjacency_*            | program       |
| aspect / slender       | spatial       |
| compactness            | spatial       |
| reachable / depth / …  | circulation  |
| privacy_transition_*   | privacy       |
| orientation_*          | environment   |
| stair / wet / site     | technical     |
| layout_stability       | robustness    |
"""

from __future__ import annotations

from packages.schema.scoring import EvaluationAxis

METRIC_OWNER: dict[str, str] = {
    "area_accuracy": EvaluationAxis.PROGRAM.value,
    "program_area_accuracy": EvaluationAxis.PROGRAM.value,
    "program_coverage": EvaluationAxis.PROGRAM.value,
    "program_fit": EvaluationAxis.PROGRAM.value,
    "required_adjacency_satisfaction": EvaluationAxis.PROGRAM.value,
    "preferred_adjacency_satisfaction": EvaluationAxis.PROGRAM.value,
    "aspect_ratio_penalty": EvaluationAxis.SPATIAL.value,
    "slender_room_count": EvaluationAxis.SPATIAL.value,
    "slender_room_ratio": EvaluationAxis.SPATIAL.value,
    "compactness": EvaluationAxis.SPATIAL.value,
    "perimeter_efficiency_pct": EvaluationAxis.SPATIAL.value,
    "space_compactness": EvaluationAxis.SPATIAL.value,
    "space_efficiency": EvaluationAxis.SPATIAL.value,
    "reachable_ratio": EvaluationAxis.CIRCULATION.value,
    "average_access_depth": EvaluationAxis.CIRCULATION.value,
    "through_room_count": EvaluationAxis.CIRCULATION.value,
    "dead_end_count": EvaluationAxis.CIRCULATION.value,
    "access_pref_satisfaction": EvaluationAxis.CIRCULATION.value,
    "privacy_transition_score": EvaluationAxis.PRIVACY.value,
    "private_through_count": EvaluationAxis.PRIVACY.value,
    "orientation_satisfaction": EvaluationAxis.ENVIRONMENT.value,
    "stair_alignment": EvaluationAxis.TECHNICAL.value,
    "wet_stack_alignment": EvaluationAxis.TECHNICAL.value,
    "setback_compliance": EvaluationAxis.TECHNICAL.value,
    "entry_on_road": EvaluationAxis.TECHNICAL.value,
    "garage_on_road": EvaluationAxis.TECHNICAL.value,
    "layout_stability": EvaluationAxis.ROBUSTNESS.value,
    "layout_stability_score": EvaluationAxis.ROBUSTNESS.value,
}


def owner_of(metric: str) -> str | None:
    return METRIC_OWNER.get(metric)

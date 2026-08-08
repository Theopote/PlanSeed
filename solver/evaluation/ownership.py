"""
Metric Ownership — Phase 3.5。

每个原始 metric 只属于一个 primary score 维度；其他模块可只读引用（findings/metrics），
但不得再次计入 total_score 加权。

| Metric                    | Primary score          |
|---------------------------|------------------------|
| area_accuracy             | program_fit            |
| program_coverage          | program_fit            |
| aspect_ratio_penalty      | geometry               |
| slender_room_count        | geometry               |
| compactness               | space_efficiency       |
| perimeter_efficiency_pct  | space_efficiency       |
| reachable_ratio 等        | circulation            |
| privacy_transition_*      | privacy                |
| layout_stability*         | layout_stability       |
| stair/wet alignment       | vertical               |
| orientation_*             | orientation            |
| setback_* / entry_on_road | site                   |
| adjacency satisfaction    | adjacency              |
"""

from __future__ import annotations

# metric → primary DesignScore 字段（不含 _score 后缀的逻辑名）
METRIC_OWNER: dict[str, str] = {
    "area_accuracy": "program_fit",
    "program_area_accuracy": "program_fit",
    "program_coverage": "program_fit",
    "program_fit": "program_fit",
    "aspect_ratio_penalty": "geometry",
    "slender_room_count": "geometry",
    "slender_room_ratio": "geometry",  # 派生展示；不计 space_efficiency 分
    "compactness": "space_efficiency",
    "perimeter_efficiency_pct": "space_efficiency",
    "space_compactness": "space_efficiency",
    "space_efficiency": "space_efficiency",
}


def owner_of(metric: str) -> str | None:
    return METRIC_OWNER.get(metric)

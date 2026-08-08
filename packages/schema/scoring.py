"""评价结果模型 — Phase 3 分数 + Phase 3.5 DesignFinding。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.layout import Violation


class FindingSeverity(StrEnum):
    """设计发现严重度 — Inspector 分组用。"""

    INFO = "info"
    POSITIVE = "positive"
    WARNING = "warning"
    PROBLEM = "problem"


class DesignFinding(BaseModel):
    """
    可解释设计发现（≠ 单纯报分数）。

    Evaluator 输出 findings；Inspector 按 severity / category 展示。
    """

    id: str = Field(description="稳定 id，如 privacy.private_through_room")
    category: str = Field(
        description="circulation | privacy | program_fit | geometry | …"
    )
    severity: FindingSeverity
    title: str
    message: str
    room_ids: list[str] = Field(default_factory=list)
    metric: str | None = None
    measured_value: float | None = None
    recommended_action: str | None = None


class DesignMetrics(BaseModel):
    """第一阶段 metrics — 可扩展。"""

    overlap_count: int = 0
    boundary_violation: int = 0
    area_error: float = 0.0
    min_width_violation: int = 0
    aspect_ratio_penalty: float = 0.0
    compactness: float = 0.0

    required_adjacency_satisfaction: float = 0.0
    preferred_adjacency_satisfaction: float = 0.0

    stair_alignment: float = 0.0
    wet_stack_alignment: float = 0.0
    wet_zone_alignment: float = Field(
        default=0.0,
        description="[deprecated] wet_stack_alignment 的别名",
    )

    setback_compliance: float = 1.0
    orientation_satisfaction: float = 1.0

    # Phase 3
    program_fit: float = 1.0
    space_efficiency: float = 1.0
    privacy_transition_score: float = 1.0
    reachable_ratio: float = 1.0
    layout_stability: float = 1.0


class DesignScore(BaseModel):
    """
    可解释建筑评价（Phase 3 + 3.5）。

    分项 score 仍用于排名；findings 才是 Inspector 主内容。
    """

    geometry_score: float = 0.0
    adjacency_score: float = 0.0
    circulation_score: float = 0.0
    orientation_score: float = 0.0
    privacy_score: float = 0.0
    vertical_score: float = 0.0
    site_score: float = 0.0
    program_fit_score: float = 0.0
    space_efficiency_score: float = 0.0
    layout_stability_score: float = 0.0

    total_score: float = 0.0

    metrics: DesignMetrics = Field(default_factory=DesignMetrics)
    findings: list[DesignFinding] = Field(
        default_factory=list,
        description="设计发现（优势 / 问题 / 警告）",
    )
    explanations: list[str] = Field(
        default_factory=list,
        description="[compat] 由 findings 派生的短标题列表",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="[compat] WARNING/PROBLEM 的 message 摘要",
    )
    violations: list[Violation] = Field(default_factory=list)

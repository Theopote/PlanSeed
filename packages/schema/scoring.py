"""评价结果模型 — 七轴评价层 + DesignFinding。"""

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


class EvaluationAxis(StrEnum):
    """用户可理解的评价轴（Phase 3.5）。"""

    PROGRAM = "program"
    SPATIAL = "spatial"
    CIRCULATION = "circulation"
    PRIVACY = "privacy"
    ENVIRONMENT = "environment"
    TECHNICAL = "technical"
    ROBUSTNESS = "robustness"


class DesignFinding(BaseModel):
    """
    可解释设计发现（≠ 单纯报分数）。

    category 应对齐 EvaluationAxis（或子域，如仍兼容旧 id）。
    """

    id: str = Field(description="稳定 id，如 privacy.private_through_room")
    category: str = Field(
        description="program | spatial | circulation | privacy | environment | technical | robustness"
    )
    severity: FindingSeverity
    title: str
    message: str
    room_ids: list[str] = Field(default_factory=list)
    metric: str | None = None
    measured_value: float | None = None
    recommended_action: str | None = None


class DesignMetrics(BaseModel):
    """底层 metrics — 可扩展；总分按七轴聚合，不按本表直接加权。"""

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

    program_fit: float = 1.0
    space_efficiency: float = 1.0
    privacy_transition_score: float = 1.0
    reachable_ratio: float = 1.0
    layout_stability: float = 1.0


class DesignScore(BaseModel):
    """
    七轴建筑评价（用户层）。

    Program / Spatial / Circulation / Privacy / Environment / Technical / Robustness
    """

    program_score: float = Field(default=0.0, description="空间清单 / 面积份额 / 邻接")
    spatial_score: float = Field(default=0.0, description="比例 / 紧凑度 / 形状")
    circulation_score: float = Field(default=0.0, description="可达 / 深度 / 穿堂")
    privacy_score: float = Field(default=0.0, description="动静分区 / 过渡 / 穿卧")
    environment_score: float = Field(default=0.0, description="朝向 / 外墙；采光后续")
    technical_score: float = Field(default=0.0, description="楼梯 / 湿区 / 入口 / 临路")
    robustness_score: float = Field(default=0.0, description="repair / reslice / 稳定性")

    total_score: float = 0.0

    metrics: DesignMetrics = Field(default_factory=DesignMetrics)
    findings: list[DesignFinding] = Field(default_factory=list)
    explanations: list[str] = Field(
        default_factory=list,
        description="[compat] 由 findings 派生",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="[compat] WARNING/PROBLEM 摘要",
    )
    violations: list[Violation] = Field(default_factory=list)

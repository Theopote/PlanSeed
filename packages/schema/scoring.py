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
    """
    用户可理解的评价轴（冻结名，至少 Phase 3.6–4 内不改）。

    标识符 / JSON / API / Desktop / Compare / docs / tests 共用这七个小写名。
    允许加深轴内底层 metric 与 ownership；禁止改轴名、禁止再拆成
    geometry/efficiency 等旧式并列分数名。
    """

    PROGRAM = "program"
    SPATIAL = "spatial"
    CIRCULATION = "circulation"
    PRIVACY = "privacy"
    ENVIRONMENT = "environment"
    TECHNICAL = "technical"
    ROBUSTNESS = "robustness"


class DesignFinding(BaseModel):
    """
    可解释设计发现（≠ 单纯报分数；≠ 法规合规结论）。

    category 应对齐 EvaluationAxis（或子域，如仍兼容旧 id）。
    文案须保持 design heuristic；禁止无 CodeProfile / Jurisdiction / Rule source
    时声称「符合规范 / 合法 / 消防 / 无障碍」等。
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

    setback_compliance: float = 1.0  # 内部名：buildable 落位比例；非法规「合规」结论

    orientation_satisfaction: float = 1.0

    program_fit: float = 1.0
    space_efficiency: float = 1.0
    privacy_transition_score: float = 1.0
    reachable_ratio: float = 1.0
    layout_stability: float = 1.0


class DesignScore(BaseModel):
    """
    七轴建筑评价（用户层）。轴名冻结，见 EvaluationAxis。

    Program / Spatial / Circulation / Privacy / Environment / Technical / Robustness
    """

    program_score: float = Field(default=0.0, description="空间清单 / 面积份额 / 邻接")
    spatial_score: float = Field(default=0.0, description="比例 / 紧凑度 / 形状")
    circulation_score: float = Field(default=0.0, description="可达 / 深度 / 穿堂")
    privacy_score: float = Field(default=0.0, description="动静分区 / 过渡 / 穿卧")
    environment_score: float = Field(
        default=0.0,
        description="Environment (Orientation MVP)：朝向 / 外墙；不含日照/通风/景观模拟",
    )
    technical_score: float = Field(
        default=0.0,
        description="Technical Logic：楼梯 / 湿区叠置 / 入口与场地；不含结构/设备/消防/法规",
    )
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


# temporary compatibility alias — Score ≠ Evaluation 语义上长期应拆分。
# 现阶段与 DesignScore 同构，避免双源；schema 稳定后再升级为真正模型，例如：
#   DesignEvaluation(score, findings, metrics, profile, evaluator_version, …)
# 候选扩展字段：evaluation_version / timestamp / profile /
# metric_ownership_version / scenario / comparison_signature
# 拆分前勿在业务层假设「Evaluation 仅等于七轴分数」。
DesignEvaluation = DesignScore

"""FastAPI 请求/响应模型（≠ solver 领域模型）。

Desktop Alpha v0.1 契约冻结（至 Phase 4 交互深化）：
GenerateResponse / CandidatePayload / DesignScore / DesignFinding /
solver_identity / CandidateProvenance — 禁止无 bump 的破坏性改字段。
详见 docs/roadmap.md。
"""

from __future__ import annotations

from typing import Any

from packages.schema.locks import LayoutLocks
from packages.schema.requirements import RequirementSpec
from packages.schema.scoring import DesignScore
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """生成请求：基准案例或 RequirementSpec。"""

    use_benchmark: bool = False
    requirements: RequirementSpec | None = None
    candidate_count: int | None = Field(default=None, ge=1, le=64)
    return_top_k: int | None = Field(default=None, ge=1, le=16)
    base_seed: int | None = Field(
        default=None,
        ge=0,
        le=1_000_000,
        description="Phase 4.2：候选种子起点；默认沿用 SolverConfig.base_seed",
    )
    locks: LayoutLocks | None = Field(
        default=None,
        description="Phase 4.1：锁定房间/楼梯后只重生成其余空间",
    )


class RoomSummary(BaseModel):
    id: str
    name: str
    category: str
    target_area: float
    floor_id: str | None = None


class ProgramSummary(BaseModel):
    project_id: str
    site_width: float
    site_depth: float
    floor_count: int
    rooms: list[RoomSummary]
    floors: list[dict[str, Any]]
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)


class CandidateProvenance(BaseModel):
    """算法契约版本；与 LayoutCandidate.provenance / metrics 对齐。"""

    solver_version: str
    generator_version: str
    evaluation_version: str


class RoomPlacementPayload(BaseModel):
    """候选上的房间放置摘要（Phase 4.0 Inspector；additive）。"""

    room_id: str
    floor_id: str
    x: float
    y: float
    width: float
    depth: float
    area: float


class CandidatePayload(BaseModel):
    id: str
    seed: int
    score: float | None
    label: str
    svg: str
    design_score: DesignScore | None = None
    validation: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    provenance: CandidateProvenance | None = None
    placements: list[RoomPlacementPayload] = Field(
        default_factory=list,
        description="RoomPlacement 摘要；前端点选房间用",
    )


class CompareRequest(BaseModel):
    """比较请求：只传两侧 evaluation，API 不做重评。"""

    evaluation_a: DesignScore
    evaluation_b: DesignScore
    label_a: str = "A"
    label_b: str = "B"


class AxisCompareRowPayload(BaseModel):
    key: str
    label: str
    score_a: float
    score_b: float


class CompareResponse(BaseModel):
    label_a: str
    label_b: str
    rows: list[AxisCompareRowPayload]
    advantages_a: list[str] = Field(default_factory=list)
    advantages_b: list[str] = Field(default_factory=list)


class RejectedCandidatePayload(BaseModel):
    """Hard-fail 无效候选摘要（≠ 有效但未进 Top-K）。"""

    id: str
    seed: int
    reasons: list[str] = Field(default_factory=list)
    constraint_ids: list[str] = Field(default_factory=list)


# 响应中最多带回多少条淘汰样例（调试 / Inspector）
MAX_REJECTED_SAMPLES = 8


class GenerateResponse(BaseModel):
    generated: int
    valid: int
    rejected: int
    program_summary: ProgramSummary
    candidates: list[CandidatePayload]
    violation_summary: dict[str, int] = Field(default_factory=dict)
    rejected_candidates: list[RejectedCandidatePayload] = Field(default_factory=list)
    solver_identity: dict[str, str] = Field(
        default_factory=dict,
        description="solver_version / generator_version / evaluation_version",
    )

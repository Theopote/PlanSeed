"""FastAPI 请求/响应模型（≠ solver 领域模型）。

Desktop Alpha v0.1 契约冻结（至 Phase 4 交互深化）：
GenerateResponse / CandidatePayload / DesignScore / DesignFinding /
solver_identity / CandidateProvenance — 禁止无 bump 的破坏性改字段。
详见 docs/roadmap.md。
"""

from __future__ import annotations

from typing import Any, Literal

from packages.schema.limits import API_LIMITS
from packages.schema.locks import LayoutLocks
from packages.schema.requirements import RequirementSpec
from packages.schema.scoring import DesignScore
from pydantic import BaseModel, Field

RevisionStatus = Literal["generated", "dirty", "validated"]


class GenerateRequest(BaseModel):
    """生成请求：基准案例或 RequirementSpec。"""

    use_benchmark: bool = False
    requirements: RequirementSpec | None = None
    candidate_count: int | None = Field(
        default=None, ge=1, le=API_LIMITS.max_generate_candidates
    )
    return_top_k: int | None = Field(
        default=None, ge=1, le=API_LIMITS.max_generate_return_top_k
    )
    base_seed: int | None = Field(
        default=None,
        ge=0,
        le=API_LIMITS.max_base_seed,
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
    """SolverProvenance（API 名保留 CandidateProvenance）；与 LayoutCandidate.provenance 对齐。"""

    solver_version: str
    generator_strategy: str = Field(
        default="guillotine",
        description="guillotine | maxrect",
    )
    generator_version: str
    selection_strategy: str | None = Field(
        default=None,
        description="axis-diverse | pareto | score | geom-diverse",
    )
    selection_version: str | None = Field(
        default=None,
        description="选优规则包版本",
    )
    evaluation_version: str
    assignment_strategy: str = Field(
        default="heuristic",
        description="heuristic | cpsat",
    )
    geometry_backend: str = Field(
        default="rect",
        description="rect | shapely-orthogonal",
    )

class RoomPlacementPayload(BaseModel):
    """候选上的房间放置摘要（Phase 4.0 Inspector；additive）。"""

    room_id: str
    floor_id: str
    x: float
    y: float
    width: float
    depth: float
    area: float


class ZonePlacementPayload(BaseModel):
    """功能分区容器摘要（Phase 4 Lock Zone；additive）。"""

    id: str | None = Field(default=None, description="如 F1-day-0")
    zone: str
    kind: str | None = Field(default=None, description="与 zone 同义")
    floor_id: str
    x: float
    y: float
    width: float
    depth: float
    room_ids: list[str] = Field(default_factory=list)


class MutationRecordPayload(BaseModel):
    """会话 mutation 历史条目（Phase 5.1）；非完整事件溯源。"""

    id: str
    kind: str
    room_id: str | None = None
    partner_room_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    after_partner: dict[str, Any] | None = None
    created_at: str | None = None


class CandidatePayload(BaseModel):
    id: str
    seed: int
    score: float | None
    label: str
    svg: str
    floor_svgs: dict[str, str] = Field(
        default_factory=dict,
        description="每层独立 SVG（serializer / render_floor_svg）；报告优先消费，禁止切 DOM",
    )
    design_score: DesignScore | None = None
    validation: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    provenance: CandidateProvenance | None = None
    variant_parent_id: str | None = Field(
        default=None,
        description="Phase 5：父候选 id",
    )
    variant_generation: int = Field(default=0, ge=0, description="Phase 5：相对根代数")
    lock_snapshot_id: str | None = Field(
        default=None,
        description="Phase 5：生成时 locks 指纹",
    )
    revision_status: RevisionStatus = Field(
        default="generated",
        description="Phase 5.1：generated | dirty | validated",
    )
    revision_id: str | None = Field(
        default=None,
        description=(
            "Phase 7：几何+评价 revision 标识；Final Export 须与 store 一致。"
            "缺省时兼容旧快照，视为等于 candidate.id"
        ),
    )
    revision_parent_id: str | None = Field(
        default=None,
        description="Phase 5.1：用户编辑派生自哪个候选 revision",
    )
    mutations: list[MutationRecordPayload] = Field(
        default_factory=list,
        description="Phase 5.1：相对 generated 基线的 mutation 日志",
    )
    placements: list[RoomPlacementPayload] = Field(
        default_factory=list,
        description="RoomPlacement 摘要；前端点选房间用",
    )
    zones: list[ZonePlacementPayload] = Field(
        default_factory=list,
        description="功能分区几何；Lock Zone 用",
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
MAX_REJECTED_SAMPLES = API_LIMITS.max_rejected_samples


class GenerateResponse(BaseModel):
    generated: int
    valid: int
    rejected: int
    program_summary: ProgramSummary
    requirement_spec: RequirementSpec | None = Field(
        default=None,
        description="Phase 5.1.1：求解用 canonical RequirementSpec（UI ProgramSummary 不可替代）",
    )
    candidates: list[CandidatePayload]
    violation_summary: dict[str, int] = Field(default_factory=dict)
    rejected_candidates: list[RejectedCandidatePayload] = Field(default_factory=list)
    solver_identity: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "SolverProvenance 默认身份："
            "solver/generator/selection/evaluation + strategy 层"
        ),
    )

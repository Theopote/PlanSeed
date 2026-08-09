"""Phase 7 — Design Report 权威文档模型（Deliverable）。

Frontend / HTML / JSON 均从此模型渲染；禁止各端重算面积或另发明评分。
Phase 7.0.1：报告须声明评价是否与几何 revision 一致（Report Integrity）。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.scoring import DesignFinding, DesignScore

# 页脚边界声明（产品定位；禁止写成「AI designed this house」）
REPORT_BOUNDARY_LINES: tuple[str, ...] = (
    "Requirement interpretation: Local LLM + deterministic semantic pipeline",
    "Geometry: PlanSeed deterministic solver",
    "Evaluation: PlanSeed residential heuristic evaluator",
    "AI interpreted design intent; deterministic solver generated and evaluated geometry.",
)


class ReportStatus(StrEnum):
    """报告相对候选 revision 的评价新鲜度。"""

    VALID = "valid"
    """geometry 与 evaluation 一致（generated / validated）。"""

    STALE_EVALUATION = "stale_evaluation"
    """几何已改（dirty），评分/Finding 可能过期 — 不得作正式评价交付。"""

    INVALID_CANDIDATE = "invalid_candidate"
    """候选缺失或无法组装。"""


class ProjectMetadata(BaseModel):
    """报告头：项目与生成语境。"""

    project_id: str | None = None
    project_name: str = "Untitled"
    generated_at: str | None = None
    app_version: str | None = None
    edited: bool = Field(
        default=False,
        description="候选是否经历用户 mutation（dirty 或 validated）",
    )


class RequirementSummary(BaseModel):
    """Key Intent — 用户可读要点，非完整 RequirementSpec。"""

    floor_count: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    has_garage: bool | None = None
    prefer_south_facing_living: bool | None = None
    site_width: float | None = None
    site_depth: float | None = None
    key_intents: list[str] = Field(
        default_factory=list,
        description="短句要点（层数/朝南/厨餐 near 等）",
    )


class ReportAssumption(BaseModel):
    key: str
    value: str | int | float | bool | None = None
    reason: str = ""
    source: str | None = None


class ReportUnknown(BaseModel):
    key: str
    description: str = ""
    priority: str | None = None


class CandidateSummary(BaseModel):
    candidate_id: str
    label: str
    seed: int | None = None
    total_score: float | None = None
    revision_status: str | None = None
    revision_parent_id: str | None = None


class FloorPlanBlock(BaseModel):
    """平面图块；SVG 由 backend 序列化候选提供，前端不重渲几何。"""

    floor_id: str = "all"
    label: str = "Floor plan"
    svg: str = ""


class RoomScheduleRow(BaseModel):
    """面积表行 — area 来自 placements（已算好），禁止 width×depth 再算。"""

    room_id: str
    name: str
    floor_id: str
    width: float
    depth: float
    area: float


class EvaluationSummary(BaseModel):
    """直接挂 DesignScore；不另发明分制。"""

    design_score: DesignScore | None = None
    evaluation_fresh: bool = Field(
        default=True,
        description="False = dirty 几何；评分可能不对应当前平面",
    )


class ReportProvenance(BaseModel):
    solver_version: str | None = None
    generator_version: str | None = None
    evaluation_version: str | None = None
    boundary_lines: list[str] = Field(
        default_factory=lambda: list(REPORT_BOUNDARY_LINES),
    )


class DesignReport(BaseModel):
    """
    Phase 7 权威交付文档。

    DesignReport → HTML / JSON /（未来）专业 PDF
    """

    status: ReportStatus = ReportStatus.VALID
    source_revision_id: str | None = Field(
        default=None,
        description="对应候选 id（交付物溯源）",
    )
    project: ProjectMetadata = Field(default_factory=ProjectMetadata)
    requirement: RequirementSummary = Field(default_factory=RequirementSummary)
    assumptions: list[ReportAssumption] = Field(default_factory=list)
    unknowns: list[ReportUnknown] = Field(default_factory=list)
    candidate: CandidateSummary
    floor_plans: list[FloorPlanBlock] = Field(default_factory=list)
    room_schedule: list[RoomScheduleRow] = Field(default_factory=list)
    evaluation: EvaluationSummary = Field(default_factory=EvaluationSummary)
    findings: list[DesignFinding] = Field(default_factory=list)
    provenance: ReportProvenance = Field(default_factory=ReportProvenance)


# API / 文档别名
DesignReportPayload = DesignReport

"""Phase 7 — Design Report 权威文档模型（Deliverable）。

Frontend / HTML / JSON 均从此模型渲染；禁止各端重算面积或另发明评分。
原则：不能生成错误报告 — 权威数据缺失时 fail loudly（非 best-effort）。
Phase 7.0.1：报告须声明评价是否与几何 revision 一致（Report Integrity）。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.report_i18n import (
    DEFAULT_REPORT_LOCALE,
    ReportLocale,
    boundary_lines_for_locale,
)
from packages.schema.report_i18n import (
    geometry_origin_label as _geometry_origin_label,
)
from packages.schema.scoring import DesignFinding, DesignScore

# 兼容旧引用：默认 locale 边界声明（新代码请用 boundary_lines_for_locale）
REPORT_BOUNDARY_LINES: tuple[str, ...] = tuple(
    boundary_lines_for_locale(DEFAULT_REPORT_LOCALE)
)


class ReportStatus(StrEnum):
    """报告相对候选 revision 的评价新鲜度。"""

    VALID = "valid"
    """geometry 与 evaluation 一致（generated / validated）。"""

    STALE_EVALUATION = "stale_evaluation"
    """几何已改（dirty），评分/Finding 可能过期 — 不得作正式评价交付。"""

    INVALID_CANDIDATE = "invalid_candidate"
    """候选缺失或无法组装。"""


class GeometryOrigin(StrEnum):
    """几何相对 Solver 的编辑状态（报告头；细于 bool edited）。"""

    SOLVER_GENERATED = "solver_generated"
    """未改：Solver 生成后的评价仍新鲜。"""

    USER_EDITED_VALIDATED = "user_edited_validated"
    """用户改过并已 revalidate — 可正式报告。"""

    USER_EDITED_STALE = "user_edited_stale"
    """用户改过且评价过期（dirty）— 禁止正式报告。"""


# 兼容：默认 zh-CN 标签；渲染请用 geometry_origin_label(locale, …)
GEOMETRY_ORIGIN_LABELS: dict[GeometryOrigin, str] = {
    o: _geometry_origin_label(DEFAULT_REPORT_LOCALE, o) for o in GeometryOrigin
}


class ProjectMetadata(BaseModel):
    """报告头：项目与生成语境。"""

    project_id: str | None = None
    project_name: str = "Untitled"
    # 实际为报告构建时间（非 candidate 生成时间）；P2 宜改名 report_generated_at
    generated_at: str | None = None
    app_version: str | None = None
    locale: ReportLocale = Field(
        default=DEFAULT_REPORT_LOCALE,
        description="报告文案 locale；Alpha 默认 zh-CN",
    )
    geometry_origin: GeometryOrigin = Field(
        default=GeometryOrigin.SOLVER_GENERATED,
        description="求解器生成 | 用户编辑·已验证 | 用户编辑·评价过期",
    )
    edited: bool = Field(
        default=False,
        description="兼容字段：geometry_origin != solver_generated（勿再单独依赖）",
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
    """
    平面图块 — SVG 由 serializer / `render_floor_svg` 提供，报告层只消费，禁止切 SVG DOM。

    - 有 `candidate.floor_svgs` 时：一块对应一层（floor_id=F1/F2/…）
    - 否则：单块 `floor_id="all"` = Candidate 整图 snapshot（旧快照兼容）
    """

    floor_id: str = Field(
        default="all",
        description='真实楼层 id（如 F1），或整图 "all"',
    )
    label: str = "Floor plan"
    svg: str = ""
    north_angle_deg: float | None = Field(
        default=None,
        description=(
            "正北相对 model north（图上方 / −Y）的顺时针角（度），"
            "与 SiteCoordinateSystem.north_angle 一致。"
            "None = 未定义：报告不得画默认 ↑N"
        ),
    )


class RoomScheduleRow(BaseModel):
    """面积表行 — area 必须来自 placements 权威字段；缺 area 则报告组装失败，禁止 width×depth。"""

    room_id: str = Field(description="调试 / Provenance 用；主表不作为首列展示")
    name: str
    floor_id: str
    width: float
    depth: float
    area: float
    target_area: float | None = Field(
        default=None,
        description="来自 DesignProgram.rooms[].target_area；缺省则差值为空",
    )
    area_delta: float | None = Field(
        default=None,
        description="实际面积 − 目标面积（仅 target_area 已知时）",
    )


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
    export_mode: str = Field(
        default="preview",
        description="preview | final；final 须来自 ProjectStore + revision_id",
    )
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
        description="候选 revision_id（Final Export 溯源；旧快照可等于 candidate.id）",
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

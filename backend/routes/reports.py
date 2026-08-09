"""Phase 7 — Design Report API。

Preview：可接受 client payload（开发 / 预览方便）。
Final Export：必须 project_id + candidate_id + revision_id，从 ProjectStore 读取。
HTML 内嵌 SVG 经 sanitize（print / srcDoc 纵深防御）。
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from packages.persistence import ProjectStore
from packages.schema.report import DesignReport, ReportStatus
from pydantic import BaseModel, Field, model_validator

from backend.routes.projects import APP_VERSION, ProjectPayload
from backend.services.report_builder import (
    ReportBuildError,
    build_design_report,
    report_status_for_candidate,
)
from backend.services.report_html import render_report_html
from backend.services.report_svg_sanitize import SvgSanitizeError
from backend.services.serialization import resolve_revision_id

router = APIRouter(tags=["reports"])

ExportMode = Literal["preview", "final"]


class BuildReportRequest(BaseModel):
    """
    preview — payload 或 project_id（可无 revision_id）
    final — 仅 project_id + candidate_id + revision_id（禁止 payload）
    """

    mode: ExportMode = Field(
        default="final",
        description="preview=可 payload；final=必须从 ProjectStore 读且校验 revision_id",
    )
    project_id: str | None = None
    candidate_id: str | None = None
    revision_id: str | None = Field(
        default=None,
        description="final 必填；须与 store 中候选 revision_id 一致",
    )
    project_name: str | None = None
    payload: ProjectPayload | None = None
    include_html: bool = True
    allow_stale_evaluation: bool = Field(
        default=False,
        description=(
            "False（默认）：dirty 拒绝正式评价报告（HTTP 409）。"
            "preview 调试可 true；final 仍建议 false。"
        ),
    )

    @model_validator(mode="after")
    def _check_mode(self) -> BuildReportRequest:
        if self.mode == "final":
            missing = [
                name
                for name, val in (
                    ("project_id", self.project_id),
                    ("candidate_id", self.candidate_id),
                    ("revision_id", self.revision_id),
                )
                if not (isinstance(val, str) and val.strip())
            ]
            if missing:
                raise ValueError(
                    "final 须提供 project_id + candidate_id + revision_id"
                    f"（缺：{', '.join(missing)}）"
                )
            if self.payload is not None:
                raise ValueError("final 禁止 client payload；请从已保存项目导出")
        else:
            if self.payload is None and not (
                isinstance(self.project_id, str) and self.project_id.strip()
            ):
                raise ValueError("preview 须提供 payload 或 project_id")
        return self


class BuildReportResponse(BaseModel):
    report: DesignReport
    html: str | None = Field(
        default=None,
        description="HTML 预览（Print/PDF）；include_html=false 时为 null",
    )


def _store() -> ProjectStore:
    return ProjectStore()


def _http_for_build_error(exc: ReportBuildError) -> HTTPException:
    status = 409 if exc.code == "invalid_candidate" else 400
    detail: dict[str, Any] = {
        "code": exc.code,
        "message": str(exc),
    }
    if exc.room_id is not None:
        detail["room_id"] = exc.room_id
    if exc.candidate_id is not None:
        detail["candidate_id"] = exc.candidate_id
    return HTTPException(status_code=status, detail=detail)


def _load_store_payload(project_id: str) -> tuple[str, str, ProjectPayload]:
    row = _store().get(project_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "project_not_found",
                "message": "项目不存在",
                "project_id": project_id,
            },
        )
    pid = str(row["id"])
    name = str(row.get("name") or "Untitled")
    try:
        payload = ProjectPayload.model_validate(row["payload"])
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "project_payload_invalid",
                "message": f"项目 payload 无效：{exc}",
            },
        ) from exc
    return pid, name, payload


def _pick_candidate(
    candidates: list[dict[str, Any]],
    *,
    candidate_id: str | None,
    allow_fallback: bool,
) -> dict[str, Any]:
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "candidates_missing",
                "message": "项目无候选，无法出报告",
            },
        )
    if candidate_id:
        for c in candidates:
            if isinstance(c, dict) and c.get("id") == candidate_id:
                return c
        raise HTTPException(
            status_code=404,
            detail={
                "code": "candidate_not_found",
                "message": f"候选不存在：{candidate_id}",
                "candidate_id": candidate_id,
            },
        )
    if not allow_fallback:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "candidate_id_required",
                "message": "须指定 candidate_id",
            },
        )
    first = candidates[0]
    if not isinstance(first, dict):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_candidate", "message": "候选格式无效"},
        )
    return first


@router.post("/api/reports/build", response_model=BuildReportResponse)
def build_report(body: BuildReportRequest) -> BuildReportResponse:
    """Preview 可 payload；Final 仅 ProjectStore + revision_id 校验。"""
    export_mode: ExportMode = body.mode
    project_id: str | None = None
    project_name = body.project_name or "Untitled"
    payload: ProjectPayload

    if export_mode == "final":
        assert body.project_id and body.candidate_id and body.revision_id
        project_id, stored_name, payload = _load_store_payload(body.project_id)
        project_name = body.project_name or stored_name
        candidate = _pick_candidate(
            list(payload.candidates or []),
            candidate_id=body.candidate_id,
            allow_fallback=False,
        )
        stored_rev = resolve_revision_id(candidate)
        if stored_rev != body.revision_id.strip():
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "revision_mismatch",
                    "message": (
                        "revision_id 与已保存候选不一致；"
                        "请重新保存/验证后再导出正式报告。"
                    ),
                    "candidate_id": candidate.get("id"),
                    "expected_revision_id": stored_rev,
                    "requested_revision_id": body.revision_id,
                },
            )
    else:
        if body.payload is not None:
            payload = body.payload
            project_id = body.project_id
            if body.project_name:
                project_name = body.project_name
        else:
            assert body.project_id
            project_id, stored_name, payload = _load_store_payload(body.project_id)
            project_name = body.project_name or stored_name

        cand_id = body.candidate_id or payload.selected_id
        candidate = _pick_candidate(
            list(payload.candidates or []),
            candidate_id=cand_id,
            allow_fallback=cand_id is None,
        )
        if body.revision_id:
            stored_rev = resolve_revision_id(candidate)
            if stored_rev and stored_rev != body.revision_id.strip():
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "revision_mismatch",
                        "message": "preview 所带 revision_id 与候选不一致",
                        "candidate_id": candidate.get("id"),
                        "expected_revision_id": stored_rev,
                        "requested_revision_id": body.revision_id,
                    },
                )

    status = report_status_for_candidate(candidate)
    # final 一律不允许 stale；preview 尊重 allow_stale_evaluation
    allow_stale = body.allow_stale_evaluation if export_mode == "preview" else False
    if status == ReportStatus.STALE_EVALUATION and not allow_stale:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "candidate_requires_revalidation",
                "message": (
                    "方案已修改，评价结果已过期。"
                    "请先重新验证后再导出正式评价报告。"
                ),
                "revision_status": candidate.get("revision_status"),
                "candidate_id": candidate.get("id"),
            },
        )
    if status == ReportStatus.INVALID_CANDIDATE and not allow_stale:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_candidate",
                "message": "候选无效（缺 id 或 placements），无法导出正式报告。",
                "candidate_id": candidate.get("id"),
            },
        )

    try:
        report = build_design_report(
            project_name=project_name,
            project_id=project_id,
            app_version=APP_VERSION,
            requirement_spec=payload.requirement_spec,
            program=payload.program,
            candidate=candidate,
            export_mode=export_mode,
        )
        html_out = render_report_html(report) if body.include_html else None
    except ReportBuildError as exc:
        raise _http_for_build_error(exc) from exc
    except SvgSanitizeError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "svg_sanitize_failed",
                "message": str(exc),
                "candidate_id": candidate.get("id"),
            },
        ) from exc
    return BuildReportResponse(report=report, html=html_out)

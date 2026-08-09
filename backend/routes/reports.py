"""Phase 7 — Design Report API（含 7.0.1 Report Integrity Gate）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from packages.persistence import ProjectStore
from packages.schema.report import DesignReport, ReportStatus
from pydantic import BaseModel, Field, model_validator

from backend.routes.projects import APP_VERSION, ProjectPayload
from backend.services.report_builder import (
    ReportAreaMissingError,
    build_design_report,
    report_status_for_candidate,
)
from backend.services.report_html import render_report_html

router = APIRouter(tags=["reports"])


class BuildReportRequest(BaseModel):
    """组装报告：可给 project_id，或直接传 payload + candidate。"""

    project_id: str | None = None
    project_name: str | None = None
    payload: ProjectPayload | None = None
    candidate_id: str | None = None
    include_html: bool = True
    allow_stale_evaluation: bool = Field(
        default=False,
        description=(
            "False（默认）：dirty 候选拒绝正式评价报告（HTTP 409）。"
            "True：仍可组装，但 DesignReport.status=stale_evaluation。"
        ),
    )

    @model_validator(mode="after")
    def _need_source(self) -> BuildReportRequest:
        if not self.project_id and self.payload is None:
            raise ValueError("须提供 project_id 或 payload")
        return self


class BuildReportResponse(BaseModel):
    report: DesignReport
    html: str | None = Field(
        default=None,
        description="HTML 预览（Print/PDF）；include_html=false 时为 null",
    )


def _store() -> ProjectStore:
    return ProjectStore()


@router.post("/api/reports/build", response_model=BuildReportResponse)
def build_report(body: BuildReportRequest) -> BuildReportResponse:
    """从项目快照 + 候选组装 DesignReport（不重评）。Dirty → 409（除非 allow_stale）。"""
    project_id = body.project_id
    project_name = body.project_name or "Untitled"
    payload: ProjectPayload

    if body.payload is not None:
        payload = body.payload
        if body.project_name:
            project_name = body.project_name
    else:
        assert body.project_id is not None
        row = _store().get(body.project_id)
        if row is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        project_id = row["id"]
        project_name = body.project_name or str(row.get("name") or "Untitled")
        try:
            payload = ProjectPayload.model_validate(row["payload"])
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"项目 payload 无效：{exc}"
            ) from exc

    candidates: list[dict[str, Any]] = list(payload.candidates or [])
    if not candidates:
        raise HTTPException(status_code=400, detail="项目无候选，无法出报告")

    # 显式 candidate_id 优先；否则用 selected_id。任一指定但找不到 → 404，禁止静默换候选。
    requested_id = body.candidate_id or payload.selected_id
    candidate: dict[str, Any] | None = None
    if requested_id:
        for c in candidates:
            if isinstance(c, dict) and c.get("id") == requested_id:
                candidate = c
                break
        if candidate is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "candidate_not_found",
                    "message": f"候选不存在：{requested_id}",
                    "candidate_id": requested_id,
                },
            )
    else:
        # 过渡：仅当未指定任何候选 id 时才 fallback 第一个（日后宜取消）
        first = candidates[0]
        if not isinstance(first, dict):
            raise HTTPException(status_code=400, detail="候选格式无效")
        candidate = first

    status = report_status_for_candidate(candidate)
    if status == ReportStatus.STALE_EVALUATION and not body.allow_stale_evaluation:
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
    if status == ReportStatus.INVALID_CANDIDATE and not body.allow_stale_evaluation:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_candidate",
                "message": "候选无效，无法导出正式报告。",
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
        )
    except ReportAreaMissingError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "placement_area_missing",
                "message": str(exc),
                "room_id": exc.room_id,
                "candidate_id": candidate.get("id"),
            },
        ) from exc
    html_out = render_report_html(report) if body.include_html else None
    return BuildReportResponse(report=report, html=html_out)

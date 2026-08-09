"""Phase 7 — Design Report API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from packages.persistence import ProjectStore
from packages.schema.report import DesignReport
from pydantic import BaseModel, Field, model_validator

from backend.routes.projects import APP_VERSION, ProjectPayload
from backend.services.report_builder import build_design_report
from backend.services.report_html import render_report_html

router = APIRouter(tags=["reports"])


class BuildReportRequest(BaseModel):
    """组装报告：可给 project_id，或直接传 payload + candidate。"""

    project_id: str | None = None
    project_name: str | None = None
    payload: ProjectPayload | None = None
    candidate_id: str | None = None
    include_html: bool = True

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
    """从项目快照 + 候选组装 DesignReport（不重评）。"""
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

    cand_id = body.candidate_id or payload.selected_id
    candidate: dict[str, Any] | None = None
    if cand_id:
        for c in candidates:
            if isinstance(c, dict) and c.get("id") == cand_id:
                candidate = c
                break
    if candidate is None:
        first = candidates[0]
        if not isinstance(first, dict):
            raise HTTPException(status_code=400, detail="候选格式无效")
        candidate = first

    report = build_design_report(
        project_name=project_name,
        project_id=project_id,
        app_version=APP_VERSION,
        requirement_spec=payload.requirement_spec,
        program=payload.program,
        candidate=candidate,
    )
    html_out = render_report_html(report) if body.include_html else None
    return BuildReportResponse(report=report, html=html_out)

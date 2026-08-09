"""Phase 7.2 — 导出路由（与 /api/reports/build 分离）。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from packages.schema.report_i18n import DEFAULT_REPORT_LOCALE, ReportLocale
from pydantic import BaseModel, Field, model_validator

from backend.services.export.final_gate import load_final_candidate
from backend.services.export.json_exporter import export_design_report_json
from backend.services.export.png_exporter import ALLOWED_PNG_SIZES, export_png
from backend.services.export.svg_exporter import (
    SvgExportError,
    content_disposition_attachment,
    export_svg,
)
from backend.services.report_builder import ReportBuildError
from backend.services.report_svg_sanitize import SvgSanitizeError

router = APIRouter(tags=["exports"])

SvgScope = Literal["floor", "snapshot", "all_floors"]
PngScope = Literal["floor", "snapshot", "all_floors"]


class SvgExportRequest(BaseModel):
    """正式 SVG 导出：必须绑定 ProjectStore revision。"""

    project_id: str
    candidate_id: str
    revision_id: str
    scope: SvgScope = Field(
        default="floor",
        description="floor=单层 · snapshot=整图 · all_floors=各层 zip",
    )
    floor_id: str | None = Field(
        default=None,
        description="scope=floor 时必填（如 F1）",
    )

    @model_validator(mode="after")
    def _floor_required(self) -> SvgExportRequest:
        if self.scope == "floor" and not (self.floor_id or "").strip():
            raise ValueError("scope=floor 时 floor_id 必填")
        return self


class PngExportRequest(BaseModel):
    """正式 PNG 导出：Canonical SVG → resvg 光栅；白底。"""

    project_id: str
    candidate_id: str
    revision_id: str
    scope: PngScope = Field(
        default="floor",
        description="floor=单层 · snapshot=整图 · all_floors=各层 zip",
    )
    floor_id: str | None = Field(
        default=None,
        description="scope=floor 时必填（如 F1）",
    )
    size: Literal[2048, 4096] = Field(
        default=2048,
        description="最长边像素：2048 或 4096",
    )

    @model_validator(mode="after")
    def _validate(self) -> PngExportRequest:
        if self.scope == "floor" and not (self.floor_id or "").strip():
            raise ValueError("scope=floor 时 floor_id 必填")
        if int(self.size) not in ALLOWED_PNG_SIZES:
            raise ValueError("size 仅支持 2048 或 4096")
        return self


def _export_http_error(exc: SvgExportError) -> HTTPException:
    status = 404 if exc.code == "floor_not_found" else 400
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc)},
    )


class ReportJsonExportRequest(BaseModel):
    """正式 DesignReport JSON：Store + revision；≠ Project Snapshot。"""

    project_id: str
    candidate_id: str
    revision_id: str
    include_svg: bool = Field(
        default=True,
        description="Alpha 默认内嵌 floor_plans[].svg（经 sanitize）",
    )
    locale: ReportLocale = Field(
        default=DEFAULT_REPORT_LOCALE,
        description="报告文案 locale；Alpha 默认 zh-CN",
    )


@router.post("/api/exports/svg")
def export_svg_endpoint(body: SvgExportRequest) -> Response:
    """
    Canonical SVG 下载。

    禁止前端 DOM outerHTML；仅 ProjectStore → floor_svgs / svg → sanitize。
    """
    _pid, project_name, _payload, candidate = load_final_candidate(
        project_id=body.project_id,
        candidate_id=body.candidate_id,
        revision_id=body.revision_id,
    )
    label = str(candidate.get("label") or candidate.get("id") or "A")
    try:
        result = export_svg(
            candidate,
            scope=body.scope,
            floor_id=body.floor_id,
            project_name=project_name,
            candidate_label=label,
        )
    except SvgExportError as exc:
        raise _export_http_error(exc) from exc

    return Response(
        content=result.body,
        media_type=result.media_type,
        headers={
            "Content-Disposition": content_disposition_attachment(
                result.filename
            ),
        },
    )


@router.post("/api/exports/png")
def export_png_endpoint(body: PngExportRequest) -> Response:
    """
    Canonical SVG → PNG（resvg）。

    禁止 HTML/Workbench 截图；白底；最长边 2048/4096。
    """
    _pid, project_name, _payload, candidate = load_final_candidate(
        project_id=body.project_id,
        candidate_id=body.candidate_id,
        revision_id=body.revision_id,
    )
    label = str(candidate.get("label") or candidate.get("id") or "A")
    try:
        result = export_png(
            candidate,
            scope=body.scope,
            floor_id=body.floor_id,
            project_name=project_name,
            candidate_label=label,
            size=int(body.size),
        )
    except SvgExportError as exc:
        raise _export_http_error(exc) from exc

    return Response(
        content=result.body,
        media_type=result.media_type,
        headers={
            "Content-Disposition": content_disposition_attachment(
                result.filename
            ),
            "X-PlanSeed-Png-Width": str(result.width),
            "X-PlanSeed-Png-Height": str(result.height),
        },
    )


@router.post("/api/exports/report-json")
def export_report_json_endpoint(body: ReportJsonExportRequest) -> Response:
    """
    DesignReport JSON 下载（交付 / 归档 / 审计）。

    禁止 Project Snapshot / candidate dump；须含 report_schema_version。
    """
    project_id, project_name, payload, candidate = load_final_candidate(
        project_id=body.project_id,
        candidate_id=body.candidate_id,
        revision_id=body.revision_id,
    )
    label = str(candidate.get("label") or candidate.get("id") or "A")
    try:
        result = export_design_report_json(
            project_id=project_id,
            project_name=project_name,
            requirement_spec=payload.requirement_spec,
            program=payload.program,
            candidate=candidate,
            candidate_label=label,
            locale=body.locale,
            include_svg=body.include_svg,
        )
    except ReportBuildError as exc:
        status = 409 if exc.code == "invalid_candidate" else 400
        detail: dict = {"code": exc.code, "message": str(exc)}
        if exc.candidate_id is not None:
            detail["candidate_id"] = exc.candidate_id
        if exc.room_id is not None:
            detail["room_id"] = exc.room_id
        raise HTTPException(status_code=status, detail=detail) from exc
    except SvgSanitizeError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "svg_sanitize_failed",
                "message": str(exc),
                "candidate_id": candidate.get("id"),
            },
        ) from exc

    return Response(
        content=result.body,
        media_type=result.media_type,
        headers={
            "Content-Disposition": content_disposition_attachment(
                result.filename
            ),
            "X-PlanSeed-Report-Schema-Version": result.report.report_schema_version,
        },
    )

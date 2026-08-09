"""Phase 7.2 — 导出路由（与 /api/reports/build 分离）。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator

from backend.services.export.final_gate import load_final_candidate
from backend.services.export.svg_exporter import (
    SvgExportError,
    content_disposition_attachment,
    export_svg,
)

router = APIRouter(tags=["exports"])

SvgScope = Literal["floor", "snapshot", "all_floors"]


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
        status = 404 if exc.code == "floor_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return Response(
        content=result.body,
        media_type=result.media_type,
        headers={
            "Content-Disposition": content_disposition_attachment(
                result.filename
            ),
        },
    )

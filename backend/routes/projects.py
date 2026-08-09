"""Phase 5 项目持久化 API · Phase 7.5-D .planseed 包。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from packages.persistence import ProjectStore
from packages.persistence.planseed_package import (
    PlanseedPackageError,
    pack_planseed,
    suggest_filename,
    unpack_planseed,
)
from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SOLVER_VERSION,
)
from packages.schema.limits import API_LIMITS
from pydantic import BaseModel, Field

from backend.services.export.svg_exporter import content_disposition_attachment

router = APIRouter(prefix="/api/projects", tags=["projects"])

# 快照容器格式（≠ 设计评价契约版本）
PROJECT_FORMAT_VERSION = "1"
APP_VERSION = "0.1.0"


def _store() -> ProjectStore:
    return ProjectStore()


class ProjectSummaryOut(BaseModel):
    id: str
    name: str
    updated_at: str


class SchemaVersions(BaseModel):
    """快照内设计溯源；Save 不得仅因保存而改写为 current。"""

    solver_version: str | None = None
    generator_strategy: str | None = None
    generator_version: str | None = None
    selection_strategy: str | None = None
    selection_version: str | None = None
    evaluation_version: str | None = None
    assignment_strategy: str | None = None
    geometry_backend: str | None = None


class ProjectMeta(BaseModel):
    format_version: str = PROJECT_FORMAT_VERSION
    app_version: str = APP_VERSION


class ProjectPayload(BaseModel):
    form: dict[str, Any] = Field(default_factory=dict)
    program: dict[str, Any] | None = None
    requirement_spec: dict[str, Any] | None = Field(
        default=None,
        description="Phase 5.1.1：canonical RequirementSpec；不可用 ProgramSummary 替代",
    )
    locks: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_id: str | None = None
    compare_id: str | None = None
    schema_versions: SchemaVersions = Field(default_factory=SchemaVersions)
    project_meta: ProjectMeta = Field(default_factory=ProjectMeta)


class SaveProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=API_LIMITS.max_project_name_chars)
    id: str | None = None
    payload: ProjectPayload


class ProjectDetail(BaseModel):
    id: str
    name: str
    updated_at: str
    payload: ProjectPayload
    evaluation_version_mismatch: bool = False
    current_evaluation_version: str = Field(default_factory=lambda: EVALUATION_VERSION)


def _infer_schema_versions(payload: dict[str, Any]) -> dict[str, str | None]:
    """保留客户端传入的设计版本；缺省时从候选 provenance 推断，仍不写成「已重评」。"""
    raw = payload.get("schema_versions") or {}
    keys = (
        "solver_version",
        "generator_strategy",
        "generator_version",
        "selection_strategy",
        "selection_version",
        "evaluation_version",
        "assignment_strategy",
        "geometry_backend",
    )
    out: dict[str, str | None] = {k: raw.get(k) for k in keys}

    for c in payload.get("candidates") or []:
        if not isinstance(c, dict):
            continue
        prov = c.get("provenance") or {}
        if not isinstance(prov, dict):
            continue
        for k in keys:
            if not out[k]:
                val = prov.get(k)
                if val is not None:
                    out[k] = str(val)
        if all(out[k] for k in ("solver_version", "generator_version", "evaluation_version")):
            # 核心三件套齐了即可停；策略字段尽力填
            if all(
                out[k]
                for k in (
                    "generator_strategy",
                    "selection_strategy",
                    "assignment_strategy",
                    "geometry_backend",
                )
            ):
                break

    return out


def _stamp_project_meta(payload: dict[str, Any]) -> None:
    """仅刷新「由哪版 App 写入」；不声称设计已用新 evaluator 重算。"""
    payload["project_meta"] = {
        "format_version": PROJECT_FORMAT_VERSION,
        "app_version": APP_VERSION,
    }
    payload["schema_versions"] = _infer_schema_versions(payload)


def _mismatch(payload: ProjectPayload) -> bool:
    stored = payload.schema_versions.evaluation_version
    if not stored:
        for c in payload.candidates:
            prov = c.get("provenance") if isinstance(c, dict) else None
            if isinstance(prov, dict) and prov.get("evaluation_version"):
                stored = prov["evaluation_version"]
                break
    if not stored:
        return False
    return stored != EVALUATION_VERSION


def _detail_from_row(row: dict[str, Any]) -> ProjectDetail:
    payload = ProjectPayload.model_validate(row["payload"])
    return ProjectDetail(
        id=row["id"],
        name=row["name"],
        updated_at=row["updated_at"],
        payload=payload,
        evaluation_version_mismatch=_mismatch(payload),
        current_evaluation_version=EVALUATION_VERSION,
    )


@router.get("")
def list_projects() -> list[ProjectSummaryOut]:
    return [
        ProjectSummaryOut(id=p.id, name=p.name, updated_at=p.updated_at)
        for p in _store().list_projects()
    ]


@router.post("")
def save_project(body: SaveProjectRequest) -> ProjectDetail:
    payload = body.payload.model_dump()
    _stamp_project_meta(payload)
    saved = _store().save(name=body.name, payload=payload, project_id=body.id)
    return _detail_from_row(saved)


@router.post("/import")
async def import_planseed_package(request: Request) -> ProjectDetail:
    """打开 / 导入 `.planseed`：请求体为 ZIP 字节；写入 ProjectStore（按包内 id upsert）。"""
    data = await request.body()
    try:
        bundle = unpack_planseed(data)
    except PlanseedPackageError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": e.code, "message": str(e)},
        ) from e

    payload = dict(bundle.payload)
    if isinstance(bundle.payload.get("schema_versions"), dict):
        payload["schema_versions"] = dict(bundle.payload["schema_versions"])
    _stamp_project_meta(payload)

    saved = _store().save(
        name=bundle.name,
        payload=payload,
        project_id=bundle.project_id,
    )
    return _detail_from_row(saved)


@router.get("/{project_id}/package")
def export_planseed_package(project_id: str) -> Response:
    """导出已保存项目为 `.planseed` ZIP。"""
    row = _store().get(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    blob = pack_planseed(
        project_id=row["id"],
        name=row["name"],
        updated_at=row["updated_at"],
        payload=row["payload"],
        app_version=APP_VERSION,
    )
    filename = suggest_filename(row["name"])
    return Response(
        content=blob,
        media_type="application/zip",
        headers={
            "Content-Disposition": content_disposition_attachment(filename),
        },
    )


@router.get("/{project_id}")
def get_project(project_id: str) -> ProjectDetail:
    row = _store().get(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _detail_from_row(row)


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict[str, bool]:
    ok = _store().delete(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"ok": True}


# 供测试断言：当前应用的算法版本（≠ 自动写入快照）
CURRENT_SOLVER_VERSION = SOLVER_VERSION
CURRENT_GENERATOR_VERSION = GENERATOR_VERSION

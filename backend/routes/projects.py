"""Phase 5 项目持久化 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from packages.persistence import ProjectStore
from packages.schema.identity import (
    EVALUATION_VERSION,
    GENERATOR_VERSION,
    SOLVER_VERSION,
)
from pydantic import BaseModel, Field

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
    generator_version: str | None = None
    evaluation_version: str | None = None


class ProjectMeta(BaseModel):
    format_version: str = PROJECT_FORMAT_VERSION
    app_version: str = APP_VERSION


class ProjectPayload(BaseModel):
    form: dict[str, Any] = Field(default_factory=dict)
    program: dict[str, Any] | None = None
    locks: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_id: str | None = None
    compare_id: str | None = None
    schema_versions: SchemaVersions = Field(default_factory=SchemaVersions)
    project_meta: ProjectMeta = Field(default_factory=ProjectMeta)


class SaveProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
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
    solver_v = raw.get("solver_version")
    gen_v = raw.get("generator_version")
    eval_v = raw.get("evaluation_version")

    for c in payload.get("candidates") or []:
        if not isinstance(c, dict):
            continue
        prov = c.get("provenance") or {}
        if not isinstance(prov, dict):
            continue
        if not solver_v:
            solver_v = prov.get("solver_version")
        if not gen_v:
            gen_v = prov.get("generator_version")
        if not eval_v:
            eval_v = prov.get("evaluation_version")
        if solver_v and gen_v and eval_v:
            break

    return {
        "solver_version": solver_v,
        "generator_version": gen_v,
        "evaluation_version": eval_v,
    }


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
        # 无评价版本：看候选 provenance
        for c in payload.candidates:
            prov = c.get("provenance") if isinstance(c, dict) else None
            if isinstance(prov, dict) and prov.get("evaluation_version"):
                stored = prov["evaluation_version"]
                break
    if not stored:
        return False
    return stored != EVALUATION_VERSION


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
    validated = ProjectPayload.model_validate(saved["payload"])
    return ProjectDetail(
        id=saved["id"],
        name=saved["name"],
        updated_at=saved["updated_at"],
        payload=validated,
        evaluation_version_mismatch=_mismatch(validated),
        current_evaluation_version=EVALUATION_VERSION,
    )


@router.get("/{project_id}")
def get_project(project_id: str) -> ProjectDetail:
    row = _store().get(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    payload = ProjectPayload.model_validate(row["payload"])
    return ProjectDetail(
        id=row["id"],
        name=row["name"],
        updated_at=row["updated_at"],
        payload=payload,
        evaluation_version_mismatch=_mismatch(payload),
        current_evaluation_version=EVALUATION_VERSION,
    )


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict[str, bool]:
    ok = _store().delete(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"ok": True}


# 供测试断言：当前应用的算法版本（≠ 自动写入快照）
CURRENT_SOLVER_VERSION = SOLVER_VERSION
CURRENT_GENERATOR_VERSION = GENERATOR_VERSION

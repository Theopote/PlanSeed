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


def _store() -> ProjectStore:
    return ProjectStore()


class ProjectSummaryOut(BaseModel):
    id: str
    name: str
    updated_at: str


class SchemaVersions(BaseModel):
    solver_version: str = Field(default_factory=lambda: SOLVER_VERSION)
    generator_version: str = Field(default_factory=lambda: GENERATOR_VERSION)
    evaluation_version: str = Field(default_factory=lambda: EVALUATION_VERSION)


class ProjectPayload(BaseModel):
    form: dict[str, Any] = Field(default_factory=dict)
    program: dict[str, Any] | None = None
    locks: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_id: str | None = None
    compare_id: str | None = None
    schema_versions: SchemaVersions = Field(default_factory=SchemaVersions)


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


@router.get("")
def list_projects() -> list[ProjectSummaryOut]:
    return [
        ProjectSummaryOut(id=p.id, name=p.name, updated_at=p.updated_at)
        for p in _store().list_projects()
    ]


@router.post("")
def save_project(body: SaveProjectRequest) -> ProjectDetail:
    payload = body.payload.model_dump()
    payload["schema_versions"] = {
        "solver_version": SOLVER_VERSION,
        "generator_version": GENERATOR_VERSION,
        "evaluation_version": EVALUATION_VERSION,
    }
    saved = _store().save(name=body.name, payload=payload, project_id=body.id)
    return ProjectDetail(
        id=saved["id"],
        name=saved["name"],
        updated_at=saved["updated_at"],
        payload=ProjectPayload.model_validate(saved["payload"]),
        evaluation_version_mismatch=False,
        current_evaluation_version=EVALUATION_VERSION,
    )


@router.get("/{project_id}")
def get_project(project_id: str) -> ProjectDetail:
    row = _store().get(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    payload = ProjectPayload.model_validate(row["payload"])
    stored_ev = payload.schema_versions.evaluation_version
    mismatch = stored_ev != EVALUATION_VERSION
    return ProjectDetail(
        id=row["id"],
        name=row["name"],
        updated_at=row["updated_at"],
        payload=payload,
        evaluation_version_mismatch=mismatch,
        current_evaluation_version=EVALUATION_VERSION,
    )


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict[str, bool]:
    ok = _store().delete(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"ok": True}

"""Final Export 共用门禁 — ProjectStore + revision + dirty/invalid。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from packages.persistence import ProjectStore
from packages.schema.report import ReportStatus

from backend.routes.projects import ProjectPayload
from backend.services.report_builder import report_status_for_candidate
from backend.services.serialization import resolve_revision_id


def load_final_candidate(
    *,
    project_id: str,
    candidate_id: str,
    revision_id: str,
) -> tuple[str, str, ProjectPayload, dict[str, Any]]:
    """
    正式导出信任边界：仅从 ProjectStore 读候选并校验 revision。

    返回 (project_id, project_name, payload, candidate)。
    """
    store = ProjectStore()
    row = store.get(project_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "project_not_found", "message": "项目不存在"},
        )
    payload = ProjectPayload.model_validate(row["payload"])
    project_name = str(row.get("name") or "Untitled")

    candidates = list(payload.candidates or [])
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail={"code": "candidates_missing", "message": "项目无候选"},
        )

    candidate: dict[str, Any] | None = None
    for c in candidates:
        if isinstance(c, dict) and c.get("id") == candidate_id:
            candidate = c
            break
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "candidate_not_found",
                "message": f"未找到候选 {candidate_id}",
                "candidate_id": candidate_id,
            },
        )

    stored_rev = resolve_revision_id(candidate)
    if stored_rev != revision_id.strip():
        raise HTTPException(
            status_code=409,
            detail={
                "code": "revision_mismatch",
                "message": (
                    "revision_id 与已保存候选不一致；"
                    "请重新保存/验证后再导出。"
                ),
                "candidate_id": candidate.get("id"),
                "expected_revision_id": stored_rev,
                "requested_revision_id": revision_id,
            },
        )

    status = report_status_for_candidate(candidate)
    if status == ReportStatus.STALE_EVALUATION:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "candidate_requires_revalidation",
                "message": (
                    "方案已修改，评价结果已过期。"
                    "请先重新验证后再导出。"
                ),
                "revision_status": candidate.get("revision_status"),
                "candidate_id": candidate.get("id"),
            },
        )
    if status == ReportStatus.INVALID_CANDIDATE:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_candidate",
                "message": (
                    "候选无效（缺 id / placements，或 validation.valid=false），"
                    "无法导出。"
                ),
                "candidate_id": candidate.get("id"),
            },
        )

    return project_id, project_name, payload, candidate

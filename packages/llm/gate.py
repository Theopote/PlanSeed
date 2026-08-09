"""LLM JSON → RequirementSpec 双 Gate 入口。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from packages.llm.boundary import GeometryForbiddenError, assert_no_geometry_payload
from packages.llm.enrich import enrich_requirement_draft
from packages.llm.semantic import (
    RequirementSemanticValidator,
    SemanticIssue,
    SemanticValidationResult,
)
from packages.schema.llm_contract import LLMRequirementDraft
from packages.schema.requirements import RequirementSpec


class LLMIngestError(ValueError):
    """解析 / 校验失败。"""

    def __init__(
        self,
        message: str,
        *,
        issues: list[SemanticIssue] | None = None,
    ) -> None:
        super().__init__(message)
        self.issues = issues or []


@dataclass(frozen=True)
class IngestResult:
    draft: LLMRequirementDraft
    spec: RequirementSpec
    semantic: SemanticValidationResult
    enrich_notes: tuple[str, ...] = ()


def ingest_llm_requirement(
    raw: dict[str, Any] | str,
    *,
    raw_text: str | None = None,
    validator: RequirementSemanticValidator | None = None,
    enrich: bool = True,
) -> IngestResult:
    """
    1) 禁几何扫描
    2) LLMRequirementDraft.model_validate
    3) 确定性 enrich（unknowns / 原文空间与关系）
    4) RequirementSemanticValidator
    5) → RequirementSpec
    """
    if isinstance(raw, str):
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMIngestError(
                f"非法 JSON：{exc}",
                issues=[
                    SemanticIssue(code="req.json", message=f"非法 JSON：{exc}"),
                ],
            ) from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise LLMIngestError(
            "LLM 输出必须是 JSON object",
            issues=[
                SemanticIssue(code="req.json_object", message="输出必须是 JSON object"),
            ],
        )

    try:
        assert_no_geometry_payload(payload)
    except GeometryForbiddenError as exc:
        raise LLMIngestError(
            str(exc),
            issues=[
                SemanticIssue(
                    code="req.geometry_forbidden",
                    message=str(exc),
                )
            ],
        ) from exc

    try:
        draft = LLMRequirementDraft.model_validate(payload)
    except ValidationError as exc:
        raise LLMIngestError(
            f"Draft schema 校验失败：{exc}",
            issues=[
                SemanticIssue(code="req.draft_schema", message=str(exc)),
            ],
        ) from exc

    if raw_text and not draft.raw_text:
        draft = draft.model_copy(update={"raw_text": raw_text})

    enrich_notes: tuple[str, ...] = ()
    if enrich:
        enriched = enrich_requirement_draft(draft)
        draft = enriched.draft
        enrich_notes = enriched.notes

    sem = (validator or RequirementSemanticValidator()).validate_draft(draft)
    if not sem.ok:
        msgs = "; ".join(i.message for i in sem.hard_issues)
        raise LLMIngestError(f"语义校验失败：{msgs}", issues=list(sem.hard_issues))

    return IngestResult(
        draft=draft,
        spec=draft.to_requirement_spec(),
        semantic=sem,
        enrich_notes=enrich_notes,
    )

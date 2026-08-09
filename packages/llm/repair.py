"""Phase 6.3 — 校验失败后的有限 JSON repair（仍禁止几何）。"""

from __future__ import annotations

import json
from typing import Any

from packages.llm.boundary import SYSTEM_PROMPT_SKELETON
from packages.llm.gate import LLMIngestError, ingest_llm_requirement
from packages.llm.ollama import OllamaResponseError
from packages.llm.parser import (
    ParseResult,
    StructuredRequirementParser,
    build_user_prompt,
)
from packages.llm.provider import LLMProvider
from packages.llm.semantic import RequirementSemanticValidator, SemanticIssue

DEFAULT_MAX_REPAIRS = 2

REPAIR_PROMPT_TEMPLATE = """上次输出未通过 PlanSeed 校验。请输出修正后的完整 LLMRequirementDraft JSON（仅 JSON，不要解释）。

校验错误：
{errors}

上次输出（可能非法，供对照）：
{previous}

原始用户需求：
{text}

要求：
- 删除一切几何字段（x/y、墙、门、SVG、placements 等）
- known / assumptions / unknowns 结构正确
- 楼层偏好须在 floor_count 范围内（F1…）
- relation_intents 无原文谓词则删除；不要因房间共现臆造 near
- 不确定的关键项放入 unknowns，不要编造
"""


class LLMRepairExhaustedError(LLMIngestError):
    """repair 次数用尽仍未通过校验。"""

    def __init__(
        self,
        message: str,
        *,
        errors: list[str],
        attempts: int,
        last_raw: dict[str, Any] | None = None,
        issues: list[SemanticIssue] | None = None,
    ) -> None:
        super().__init__(message, issues=issues or [])
        self.errors = errors
        self.attempts = attempts
        self.last_raw = last_raw


def build_repair_prompt(
    text: str,
    *,
    errors: list[str],
    previous: dict[str, Any] | str | None,
) -> str:
    if isinstance(previous, dict):
        prev_s = json.dumps(previous, ensure_ascii=False, indent=2)
    elif isinstance(previous, str) and previous.strip():
        prev_s = previous.strip()
    else:
        prev_s = "(无可用 JSON)"
    err_s = "\n".join(f"- {e}" for e in errors) if errors else "- (未知错误)"
    return REPAIR_PROMPT_TEMPLATE.format(
        errors=err_s,
        previous=prev_s,
        text=text.strip(),
    )


def _is_repairable(exc: BaseException) -> bool:
    return isinstance(exc, (LLMIngestError, OllamaResponseError))


def parse_requirement_text_with_repair(
    text: str,
    *,
    provider: LLMProvider,
    system: str = SYSTEM_PROMPT_SKELETON,
    validator: RequirementSemanticValidator | None = None,
    max_repairs: int = DEFAULT_MAX_REPAIRS,
    enrich: bool = True,
) -> ParseResult:
    """
    带有限 repair 的 NL→RequirementSpec。

    max_repairs=2 → 最多 1 次初试 + 2 次修复（共 3 次 complete_json）。
    """
    if max_repairs < 0:
        raise ValueError("max_repairs 不能为负")

    cleaned = text.strip()
    user = build_user_prompt(cleaned)
    notes: list[str] = []
    last_raw: dict[str, Any] | None = None
    last_exc: BaseException | None = None
    max_attempts = max_repairs + 1

    for attempt in range(max_attempts):
        try:
            raw = provider.complete_json(system=system, user=user)
            if isinstance(raw, dict):
                last_raw = raw
            ingest = ingest_llm_requirement(
                raw,
                raw_text=cleaned,
                validator=validator,
                enrich=enrich,
            )
            return ParseResult(
                text=cleaned,
                raw=raw if isinstance(raw, dict) else last_raw or {},
                ingest=ingest,
                attempts=attempt + 1,
                repair_notes=tuple(notes),
            )
        except Exception as exc:
            if not _is_repairable(exc):
                raise
            last_exc = exc
            msg = str(exc)
            notes.append(msg)
            if attempt >= max_repairs:
                break
            # 下一轮用 repair 提示；累积列出本次为止的错误
            user = build_repair_prompt(
                cleaned,
                errors=notes,
                previous=last_raw,
            )

    raise LLMRepairExhaustedError(
        f"校验/repair 耗尽（attempts={max_attempts}）：{notes[-1] if notes else 'unknown'}",
        errors=list(notes),
        attempts=max_attempts,
        last_raw=last_raw,
        issues=_issues_from_exc(last_exc),
    ) from last_exc


def _issues_from_exc(exc: BaseException | None) -> list[SemanticIssue]:
    if isinstance(exc, LLMIngestError) and exc.issues:
        return list(exc.issues)
    if isinstance(exc, OllamaResponseError):
        return [SemanticIssue(code="req.json", message=str(exc))]
    return []


def parse_with_repair(
    parser: StructuredRequirementParser,
    text: str,
    *,
    max_repairs: int = DEFAULT_MAX_REPAIRS,
) -> ParseResult:
    """在已有 StructuredRequirementParser 上启用 repair。"""
    return parse_requirement_text_with_repair(
        text,
        provider=parser.provider,
        system=parser.system,
        validator=parser.validator,
        max_repairs=max_repairs,
        enrich=parser.enrich,
    )

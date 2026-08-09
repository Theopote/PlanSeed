"""Benchmark 失败归因（schema / semantic / geometry / JSON / repair）。"""

from __future__ import annotations

from enum import StrEnum

from packages.llm.boundary import GeometryForbiddenError
from packages.llm.gate import LLMIngestError
from packages.llm.ollama import OllamaResponseError
from packages.llm.repair import LLMRepairExhaustedError
from packages.llm.semantic import SemanticIssue

_JSON_CODES = frozenset({"req.json", "req.json_object"})
_GEOMETRY_CODES = frozenset({"req.geometry_forbidden"})
_SCHEMA_CODES = frozenset({"req.draft_schema"})


class FailureKind(StrEnum):
    SCHEMA_FAIL = "schema_fail"
    SEMANTIC_FAIL = "semantic_fail"
    GEOMETRY_VIOLATION = "geometry_violation"
    JSON_PARSE_FAIL = "json_parse_fail"
    OTHER = "other"


def classify_issue_codes(codes: list[str] | set[str]) -> FailureKind | None:
    """按优先级归类 issue code（geometry > json > schema > semantic）。"""
    code_set = set(codes)
    if not code_set:
        return None
    if code_set & _GEOMETRY_CODES:
        return FailureKind.GEOMETRY_VIOLATION
    if code_set & _JSON_CODES:
        return FailureKind.JSON_PARSE_FAIL
    if code_set & _SCHEMA_CODES:
        return FailureKind.SCHEMA_FAIL
    # 其余 hard semantic（floor / relation / …）
    return FailureKind.SEMANTIC_FAIL


def classify_failure(exc: BaseException | None) -> FailureKind | None:
    """从异常归类主因；成功路径返回 None。"""
    if exc is None:
        return None
    if isinstance(exc, GeometryForbiddenError):
        return FailureKind.GEOMETRY_VIOLATION
    if isinstance(exc, OllamaResponseError):
        return FailureKind.JSON_PARSE_FAIL
    if isinstance(exc, LLMIngestError):
        codes = [i.code for i in exc.issues]
        kind = classify_issue_codes(codes)
        if kind is not None:
            return kind
        # repair 耗尽但未带 issues：看 message 粗分
        if isinstance(exc, LLMRepairExhaustedError):
            return FailureKind.OTHER
        return FailureKind.OTHER
    return FailureKind.OTHER


def issues_codes(issues: list[SemanticIssue]) -> list[str]:
    return [i.code for i in issues]

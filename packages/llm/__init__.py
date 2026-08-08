"""Phase 6 — Local LLM 适配层（Provider / Gate；不含几何）。"""

from packages.llm.boundary import (
    FORBIDDEN_GEOMETRY_KEYS,
    SYSTEM_PROMPT_SKELETON,
    GeometryForbiddenError,
    assert_no_geometry_payload,
)
from packages.llm.gate import IngestResult, ingest_llm_requirement
from packages.llm.mock import MockLLMProvider
from packages.llm.provider import LLMProvider
from packages.llm.semantic import (
    RequirementSemanticValidator,
    SemanticIssue,
    SemanticValidationResult,
)

__all__ = [
    "FORBIDDEN_GEOMETRY_KEYS",
    "SYSTEM_PROMPT_SKELETON",
    "GeometryForbiddenError",
    "assert_no_geometry_payload",
    "IngestResult",
    "ingest_llm_requirement",
    "MockLLMProvider",
    "LLMProvider",
    "RequirementSemanticValidator",
    "SemanticIssue",
    "SemanticValidationResult",
]

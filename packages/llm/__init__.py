"""Phase 6 — Local LLM 适配层（Provider / Gate；不含几何）。"""

from packages.llm.boundary import (
    FORBIDDEN_GEOMETRY_KEYS,
    SYSTEM_PROMPT_SKELETON,
    GeometryForbiddenError,
    assert_no_geometry_payload,
)
from packages.llm.draft_schema import draft_json_schema
from packages.llm.factory import (
    create_llm_provider,
    create_requirement_llm_provider,
    load_ollama_config,
    resolve_provider_kind,
)
from packages.llm.gate import IngestResult, LLMIngestError, ingest_llm_requirement
from packages.llm.mock import MockLLMProvider
from packages.llm.ollama import (
    OllamaConfig,
    OllamaConnectionError,
    OllamaError,
    OllamaHTTPError,
    OllamaProvider,
    OllamaResponseError,
)
from packages.llm.parser import (
    ParseResult,
    StructuredRequirementParser,
    build_user_prompt,
    parse_requirement_text,
)
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
    "LLMIngestError",
    "ingest_llm_requirement",
    "MockLLMProvider",
    "LLMProvider",
    "OllamaConfig",
    "OllamaConnectionError",
    "OllamaError",
    "OllamaHTTPError",
    "OllamaProvider",
    "OllamaResponseError",
    "ParseResult",
    "StructuredRequirementParser",
    "build_user_prompt",
    "create_llm_provider",
    "create_requirement_llm_provider",
    "draft_json_schema",
    "load_ollama_config",
    "parse_requirement_text",
    "resolve_provider_kind",
    "RequirementSemanticValidator",
    "SemanticIssue",
    "SemanticValidationResult",
]

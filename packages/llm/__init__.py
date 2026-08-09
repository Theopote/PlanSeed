"""Phase 6 — Hybrid Semantic Parser（Local LLM + enrich + vocab + gate + repair）。

正式说明：docs/hybrid-semantic-parser.md。不含几何。
"""

from packages.llm.boundary import (
    FORBIDDEN_GEOMETRY_KEYS,
    SYSTEM_PROMPT_SKELETON,
    GeometryForbiddenError,
    assert_no_geometry_payload,
)
from packages.llm.draft_schema import draft_json_schema
from packages.llm.enrich import enrich_requirement_draft, extract_space_names
from packages.llm.factory import (
    create_llm_provider,
    create_requirement_llm_provider,
    load_ollama_config,
    resolve_provider_kind,
)
from packages.llm.gate import IngestResult, LLMIngestError, ingest_llm_requirement
from packages.llm.health import (
    LlmHealthState,
    LlmHealthStatus,
    model_missing_message,
    probe_llm_health,
)
from packages.llm.mock import MockLLMProvider
from packages.llm.ollama import (
    OllamaConfig,
    OllamaConnectionError,
    OllamaError,
    OllamaHTTPError,
    OllamaProvider,
    OllamaResponseError,
    model_name_matches,
)
from packages.llm.parser import (
    ParseResult,
    StructuredRequirementParser,
    build_user_prompt,
    parse_requirement_text,
)
from packages.llm.provider import LLMProvider
from packages.llm.repair import (
    DEFAULT_MAX_REPAIRS,
    LLMRepairExhaustedError,
    build_repair_prompt,
    parse_requirement_text_with_repair,
    parse_with_repair,
)
from packages.llm.runtime import (
    close_shared_requirement_provider,
    get_shared_requirement_provider,
    reset_shared_requirement_provider,
    set_shared_requirement_provider,
)
from packages.llm.semantic import (
    RequirementSemanticValidator,
    SemanticIssue,
    SemanticValidationResult,
)

__all__ = [
    "FORBIDDEN_GEOMETRY_KEYS",
    "SYSTEM_PROMPT_SKELETON",
    "DEFAULT_MAX_REPAIRS",
    "GeometryForbiddenError",
    "assert_no_geometry_payload",
    "IngestResult",
    "LLMIngestError",
    "LLMRepairExhaustedError",
    "LlmHealthState",
    "LlmHealthStatus",
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
    "build_repair_prompt",
    "build_user_prompt",
    "close_shared_requirement_provider",
    "create_llm_provider",
    "create_requirement_llm_provider",
    "draft_json_schema",
    "enrich_requirement_draft",
    "extract_space_names",
    "get_shared_requirement_provider",
    "load_ollama_config",
    "model_missing_message",
    "model_name_matches",
    "parse_requirement_text",
    "parse_requirement_text_with_repair",
    "parse_with_repair",
    "probe_llm_health",
    "reset_shared_requirement_provider",
    "resolve_provider_kind",
    "set_shared_requirement_provider",
    "RequirementSemanticValidator",
    "SemanticIssue",
    "SemanticValidationResult",
]

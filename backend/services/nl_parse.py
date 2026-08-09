"""自然语言 → RequirementSpec（Phase 6.5；不写几何）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from packages.llm import (
    LLMIngestError,
    LLMRepairExhaustedError,
    OllamaConnectionError,
    OllamaHTTPError,
    ParseResult,
    parse_requirement_text_with_repair,
    resolve_provider_kind,
)
from packages.llm.provider import LLMProvider
from packages.llm.runtime import get_shared_requirement_provider
from packages.schema.requirements import RequirementSpec

ProviderFactory = Callable[[], LLMProvider]

_provider_factory: ProviderFactory | None = None


def set_nl_provider_factory(factory: ProviderFactory | None) -> None:
    """测试注入；生产保持 None → 共享 Application LLM Runtime。"""
    global _provider_factory
    _provider_factory = factory


def get_nl_provider() -> LLMProvider:
    """
    解析用 Provider。

    - 测试工厂优先（可每次新 Mock）
    - 否则进程内共享 OllamaProvider（复用 httpx.Client）
    """
    if _provider_factory is not None:
        return _provider_factory()
    return get_shared_requirement_provider()


@dataclass(frozen=True)
class NLParseOutcome:
    spec: RequirementSpec
    attempts: int
    repair_notes: tuple[str, ...]
    provider: str
    raw: dict


def parse_nl_requirement(
    text: str,
    *,
    max_repairs: int = 2,
    provider: LLMProvider | None = None,
) -> NLParseOutcome:
    """
    NL → Draft → Gate（含有限 repair）→ RequirementSpec。

    抛出：
    - LLMIngestError / LLMRepairExhaustedError → 调用方映射 400
    - OllamaConnectionError / OllamaHTTPError → 503
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise LLMIngestError("需求文本为空")

    prov = provider or get_nl_provider()
    kind = resolve_provider_kind()
    # 若注入了 mock 工厂，报告 mock
    if _provider_factory is not None:
        kind = "mock"

    try:
        result: ParseResult = parse_requirement_text_with_repair(
            cleaned,
            provider=prov,
            max_repairs=max_repairs,
        )
    except (OllamaConnectionError, OllamaHTTPError):
        raise
    except LLMRepairExhaustedError:
        raise
    except LLMIngestError:
        raise

    return NLParseOutcome(
        spec=result.spec,
        attempts=result.attempts,
        repair_notes=result.repair_notes,
        provider=kind,
        raw=result.raw,
    )

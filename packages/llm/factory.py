"""LLMProvider 工厂 — 业务层从此取实现，勿散落 Ollama URL。"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Literal

from packages.llm.draft_schema import draft_json_schema
from packages.llm.mock import MockLLMProvider
from packages.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_S,
    OllamaConfig,
    OllamaProvider,
)
from packages.llm.provider import LLMProvider

ProviderKind = Literal["ollama", "mock"]


def load_ollama_config(
    *,
    environ: dict[str, str] | None = None,
) -> OllamaConfig:
    env = environ if environ is not None else os.environ
    timeout_raw = env.get("PLANSEED_OLLAMA_TIMEOUT", str(DEFAULT_OLLAMA_TIMEOUT_S))
    try:
        timeout_s = float(timeout_raw)
    except ValueError as exc:
        raise ValueError(
            f"PLANSEED_OLLAMA_TIMEOUT 必须是数字，收到 {timeout_raw!r}"
        ) from exc
    return OllamaConfig(
        base_url=env.get("PLANSEED_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        model=env.get("PLANSEED_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        timeout_s=timeout_s,
    )


def resolve_provider_kind(
    *,
    environ: dict[str, str] | None = None,
    default: ProviderKind = "ollama",
) -> ProviderKind:
    env = environ if environ is not None else os.environ
    raw = (env.get("PLANSEED_LLM_PROVIDER") or default).strip().lower()
    if raw not in ("ollama", "mock"):
        raise ValueError(
            f"PLANSEED_LLM_PROVIDER 须为 ollama|mock，收到 {raw!r}"
        )
    return raw  # type: ignore[return-value]


def create_llm_provider(
    kind: ProviderKind | None = None,
    *,
    environ: dict[str, str] | None = None,
    mock_responses: list[dict[str, Any]] | None = None,
    ollama_config: OllamaConfig | None = None,
    ollama_client: Any | None = None,
) -> LLMProvider:
    """
    创建 Provider。

    - kind=None → 读 PLANSEED_LLM_PROVIDER（默认 ollama）
    - mock 须提供 mock_responses（测试/离线）
    """
    resolved = kind or resolve_provider_kind(environ=environ)
    if resolved == "mock":
        if mock_responses is None:
            raise ValueError("create_llm_provider(kind='mock') 需要 mock_responses")
        return MockLLMProvider(mock_responses)
    cfg = ollama_config or load_ollama_config(environ=environ)
    return OllamaProvider(cfg, client=ollama_client)


def create_requirement_llm_provider(
    *,
    environ: dict[str, str] | None = None,
    mock_responses: list[dict[str, Any]] | None = None,
    ollama_client: Any | None = None,
) -> LLMProvider:
    """
    需求解析专用 Provider。

    - PLANSEED_LLM_PROVIDER=mock → Mock（须 mock_responses）
    - 默认 ollama，且 format= LLMRequirementDraft JSON Schema（6.2）
    """
    kind = resolve_provider_kind(environ=environ)
    if kind == "mock":
        return create_llm_provider(
            "mock",
            environ=environ,
            mock_responses=mock_responses,
        )
    cfg = replace(
        load_ollama_config(environ=environ),
        response_format=draft_json_schema(),
    )
    return create_llm_provider(
        "ollama",
        environ=environ,
        ollama_config=cfg,
        ollama_client=ollama_client,
    )

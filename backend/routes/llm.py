"""LLM 健康状态路由 — 与 Engine /api/health 并列。"""

from __future__ import annotations

from fastapi import APIRouter
from packages.llm.factory import resolve_provider_kind
from packages.llm.health import probe_llm_health
from packages.llm.ollama import OllamaProvider
from packages.llm.runtime import get_shared_requirement_provider

router = APIRouter(tags=["llm"])


@router.get("/api/llm/status")
def llm_status() -> dict:
    """
    探测 Ollama / 配置模型是否就绪。

    不下载模型；ModelMissing 时 detail 提示用户自行 ollama pull。
    """
    if resolve_provider_kind() == "mock":
        return probe_llm_health().to_dict()
    shared = get_shared_requirement_provider()
    provider = shared if isinstance(shared, OllamaProvider) else None
    return probe_llm_health(provider=provider).to_dict()

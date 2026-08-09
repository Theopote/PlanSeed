"""LLM 健康状态 — 与 EngineLifecycle（STARTING/READY/…）并列，不混用。

Idle 探测（GET /api/llm/status）：
  LLMUnavailable | ModelMissing | ModelReady

会话态（前端解析过程）：
  ParseRunning | ParseFailed
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from packages.llm.factory import (
    load_ollama_config,
    resolve_provider_kind,
)
from packages.llm.ollama import (
    DEFAULT_OLLAMA_MODEL,
    OllamaConnectionError,
    OllamaError,
    OllamaProvider,
)


class LlmHealthState(str, Enum):
    LLM_UNAVAILABLE = "LLMUnavailable"
    MODEL_MISSING = "ModelMissing"
    MODEL_READY = "ModelReady"
    PARSE_RUNNING = "ParseRunning"
    PARSE_FAILED = "ParseFailed"


@dataclass(frozen=True)
class LlmHealthStatus:
    state: LlmHealthState
    provider: str
    model: str
    detail: str | None = None
    installed_models: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "provider": self.provider,
            "model": self.model,
            "detail": self.detail,
            "installed_models": list(self.installed_models),
        }


def model_missing_message(model: str) -> str:
    """Alpha：不引导应用内 pull；提示用户用 Ollama 自行安装。"""
    return f"未检测到 {model}，请先通过 Ollama 安装。"


def probe_llm_health(
    *,
    environ: dict[str, str] | None = None,
    provider: Any | None = None,
) -> LlmHealthStatus:
    """
    探测当前需求解析 LLM 是否可用。

    - mock → ModelReady（无外部依赖）
    - ollama → tags 可达且配置模型已安装 → ModelReady
    - 禁止在此路径触发模型下载
    """
    kind = resolve_provider_kind(environ=environ)
    cfg = load_ollama_config(environ=environ)
    model = cfg.model or DEFAULT_OLLAMA_MODEL

    if kind == "mock":
        return LlmHealthStatus(
            state=LlmHealthState.MODEL_READY,
            provider="mock",
            model=model,
            detail="mock provider（无需本机模型）",
        )

    owns_client = False
    ollama = provider if isinstance(provider, OllamaProvider) else None
    if ollama is None:
        # 短超时探测，避免 health 卡住 UI
        probe_cfg = replace(cfg, timeout_s=min(cfg.timeout_s, 5.0))
        ollama = OllamaProvider(probe_cfg)
        owns_client = True

    try:
        if not ollama.is_available():
            return LlmHealthStatus(
                state=LlmHealthState.LLM_UNAVAILABLE,
                provider="ollama",
                model=model,
                detail=f"无法连接 Ollama（{cfg.base_url}）",
            )
        try:
            installed = tuple(ollama.list_models())
        except OllamaConnectionError as exc:
            return LlmHealthStatus(
                state=LlmHealthState.LLM_UNAVAILABLE,
                provider="ollama",
                model=model,
                detail=str(exc),
            )
        except OllamaError as exc:
            return LlmHealthStatus(
                state=LlmHealthState.LLM_UNAVAILABLE,
                provider="ollama",
                model=model,
                detail=str(exc),
            )

        if not ollama.is_model_available(model):
            return LlmHealthStatus(
                state=LlmHealthState.MODEL_MISSING,
                provider="ollama",
                model=model,
                detail=model_missing_message(model),
                installed_models=installed,
            )
        return LlmHealthStatus(
            state=LlmHealthState.MODEL_READY,
            provider="ollama",
            model=model,
            detail=None,
            installed_models=installed,
        )
    finally:
        if owns_client:
            ollama.close()

"""LLM 健康状态 — 与 EngineLifecycle（STARTING/READY/…）并列，不混用。

Idle 探测（GET /api/llm/status）：
  LLMUnavailable | ModelMissing | ModelReady

会话态（前端解析过程）：
  ParseRunning | ParseFailed
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
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
from packages.llm.privacy import (
    OllamaRemoteBlockedError,
    ollama_endpoint_is_loopback,
    remote_model_warning,
)


class LlmHealthState(StrEnum):
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
    base_url: str | None = None
    endpoint_remote: bool = False
    remote_blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "provider": self.provider,
            "model": self.model,
            "detail": self.detail,
            "installed_models": list(self.installed_models),
            "base_url": self.base_url,
            "endpoint_remote": self.endpoint_remote,
            "remote_blocked": self.remote_blocked,
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
    - 非 loopback 且未 ALLOW_REMOTE → LLMUnavailable + REMOTE MODEL WARNING
    - 禁止在此路径触发模型下载
    """
    kind = resolve_provider_kind(environ=environ)
    cfg = load_ollama_config(environ=environ)
    model = cfg.model or DEFAULT_OLLAMA_MODEL
    remote = not ollama_endpoint_is_loopback(cfg.base_url)

    if kind == "mock":
        return LlmHealthStatus(
            state=LlmHealthState.MODEL_READY,
            provider="mock",
            model=model,
            detail="mock provider（无需本机模型）",
            base_url=None,
            endpoint_remote=False,
            remote_blocked=False,
        )

    if remote:
        try:
            from packages.llm.privacy import enforce_ollama_endpoint_policy

            enforce_ollama_endpoint_policy(cfg.base_url, environ=environ)
        except OllamaRemoteBlockedError as exc:
            return LlmHealthStatus(
                state=LlmHealthState.LLM_UNAVAILABLE,
                provider="ollama",
                model=model,
                detail=str(exc),
                base_url=cfg.base_url,
                endpoint_remote=True,
                remote_blocked=True,
            )

    owns_client = False
    ollama = provider if isinstance(provider, OllamaProvider) else None
    if ollama is None:
        # 短超时探测，避免 health 卡住 UI
        probe_cfg = replace(cfg, timeout_s=min(cfg.timeout_s, 5.0))
        ollama = OllamaProvider(
            probe_cfg, environ=environ, skip_endpoint_policy=True
        )
        owns_client = True

    warn = remote_model_warning(cfg.base_url) if remote else None

    try:
        if not ollama.is_available():
            detail = f"无法连接 Ollama（{cfg.base_url}）"
            if warn:
                detail = f"{warn} · {detail}"
            return LlmHealthStatus(
                state=LlmHealthState.LLM_UNAVAILABLE,
                provider="ollama",
                model=model,
                detail=detail,
                base_url=cfg.base_url,
                endpoint_remote=remote,
                remote_blocked=False,
            )
        try:
            installed = tuple(ollama.list_models())
        except OllamaConnectionError as exc:
            detail = str(exc)
            if warn:
                detail = f"{warn} · {detail}"
            return LlmHealthStatus(
                state=LlmHealthState.LLM_UNAVAILABLE,
                provider="ollama",
                model=model,
                detail=detail,
                base_url=cfg.base_url,
                endpoint_remote=remote,
                remote_blocked=False,
            )
        except OllamaError as exc:
            detail = str(exc)
            if warn:
                detail = f"{warn} · {detail}"
            return LlmHealthStatus(
                state=LlmHealthState.LLM_UNAVAILABLE,
                provider="ollama",
                model=model,
                detail=detail,
                base_url=cfg.base_url,
                endpoint_remote=remote,
                remote_blocked=False,
            )

        if not ollama.is_model_available(model):
            detail = model_missing_message(model)
            if warn:
                detail = f"{warn} · {detail}"
            return LlmHealthStatus(
                state=LlmHealthState.MODEL_MISSING,
                provider="ollama",
                model=model,
                detail=detail,
                installed_models=installed,
                base_url=cfg.base_url,
                endpoint_remote=remote,
                remote_blocked=False,
            )
        return LlmHealthStatus(
            state=LlmHealthState.MODEL_READY,
            provider="ollama",
            model=model,
            detail=warn,
            installed_models=installed,
            base_url=cfg.base_url,
            endpoint_remote=remote,
            remote_blocked=False,
        )
    finally:
        if owns_client:
            ollama.close()

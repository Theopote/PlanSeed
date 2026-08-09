"""Application LLM Runtime — 进程内共享 Provider（复用 httpx 连接池）。

生产路径应通过本模块取需求解析 Provider，避免每次 parse 新建
`OllamaProvider` / `httpx.Client` 却不 close。

测试可 `set_shared_requirement_provider(...)` 注入；`reset` 会关闭
运行时自建的实例。
"""

from __future__ import annotations

import atexit
import threading
from typing import Any

from packages.llm.factory import create_requirement_llm_provider
from packages.llm.provider import LLMProvider

_lock = threading.Lock()
_shared: LLMProvider | None = None
_owns_shared: bool = False


def _close_provider(provider: LLMProvider | None) -> None:
    if provider is None:
        return
    close = getattr(provider, "close", None)
    if callable(close):
        close()


def get_shared_requirement_provider(
    *,
    environ: dict[str, str] | None = None,
    ollama_client: Any | None = None,
) -> LLMProvider:
    """
    返回进程内共享的需求解析 Provider（懒创建）。

    首次调用时 `create_requirement_llm_provider()`；之后复用同一实例。
    environ / ollama_client 仅在首次创建时生效。
    """
    global _shared, _owns_shared
    with _lock:
        if _shared is None:
            _shared = create_requirement_llm_provider(
                environ=environ,
                ollama_client=ollama_client,
            )
            _owns_shared = True
        return _shared


def set_shared_requirement_provider(provider: LLMProvider | None) -> None:
    """
    注入或清空共享 Provider（测试 / 特殊宿主）。

    若先前实例由 runtime 自建，会先 close。注入的实例由调用方负责生命周期
    （reset/set(None) 时不 close 注入实例，除非再次 set 替换前曾标记 owned）。
    """
    global _shared, _owns_shared
    with _lock:
        if _owns_shared:
            _close_provider(_shared)
        _shared = provider
        _owns_shared = False


def reset_shared_requirement_provider() -> None:
    """关闭并丢弃共享 Provider（若由 runtime 自建）。"""
    global _shared, _owns_shared
    with _lock:
        if _owns_shared:
            _close_provider(_shared)
        _shared = None
        _owns_shared = False


def close_shared_requirement_provider() -> None:
    """进程退出或显式关停时调用。"""
    reset_shared_requirement_provider()


atexit.register(close_shared_requirement_provider)

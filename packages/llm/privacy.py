"""Ollama 端点隐私守卫 — Phase 7.5-I。

Alpha 默认仅允许 loopback（127.0.0.1 / localhost / ::1）。
非本机须显式 PLANSEED_OLLAMA_ALLOW_REMOTE=1。
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from packages.llm.ollama import OllamaError

LOOPBACK_HOSTS = frozenset(
    {
        "127.0.0.1",
        "localhost",
        "::1",
        "0:0:0:0:0:0:0:1",
    }
)

REMOTE_WARNING_PREFIX = "REMOTE MODEL WARNING"


class OllamaRemoteBlockedError(OllamaError):
    """非 loopback Ollama 且未允许 remote。"""


def ollama_host(base_url: str) -> str:
    host = urlparse((base_url or "").strip()).hostname
    return (host or "").lower()


def ollama_endpoint_is_loopback(base_url: str) -> bool:
    return ollama_host(base_url) in LOOPBACK_HOSTS


def ollama_remote_allowed(*, environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    raw = (env.get("PLANSEED_OLLAMA_ALLOW_REMOTE") or "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def remote_model_warning(base_url: str) -> str:
    return (
        f"{REMOTE_WARNING_PREFIX}: Ollama 指向非本机（{base_url}）。"
        "PlanSeed 为 local-first；生产请用 loopback。"
        "若确需远程，设置 PLANSEED_OLLAMA_ALLOW_REMOTE=1。"
    )


def enforce_ollama_endpoint_policy(
    base_url: str,
    *,
    environ: dict[str, str] | None = None,
) -> None:
    """非 loopback 且未允许 → 抛 OllamaRemoteBlockedError。"""
    if ollama_endpoint_is_loopback(base_url):
        return
    if ollama_remote_allowed(environ=environ):
        return
    raise OllamaRemoteBlockedError(remote_model_warning(base_url))

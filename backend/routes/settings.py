"""应用设置 API — 读写 ~/.planseed/settings.json 并热重载 LLM Provider。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Query
from packages.llm.factory import load_ollama_config
from packages.llm.health import probe_llm_health
from packages.llm.ollama import OllamaConnectionError, OllamaError, OllamaProvider
from packages.llm.privacy import enforce_ollama_endpoint_policy
from packages.llm.runtime import reset_shared_requirement_provider
from packages.settings.models import AppSettings, LlmSettings, SettingsResponse
from packages.settings.store import (
    apply_settings_to_environ,
    read_effective_settings,
    save_persisted_settings,
)
from pydantic import BaseModel, Field

router = APIRouter(tags=["settings"])


class SettingsUpdateBody(BaseModel):
    """PUT /api/settings — 仅接受 llm 段（局部更新）。"""

    llm: LlmSettings


class SettingsUpdateResponse(BaseModel):
    settings: SettingsResponse
    llm_health: dict[str, Any]


class OllamaModelsResponse(BaseModel):
    base_url: str
    models: list[str] = Field(default_factory=list)
    reachable: bool
    detail: str | None = None


def _probe_models_at(base_url: str, *, allow_remote: bool) -> OllamaModelsResponse:
    draft = LlmSettings(ollama_base_url=base_url, ollama_allow_remote=allow_remote)
    probe_env: dict[str, str] = {
        "PLANSEED_OLLAMA_BASE_URL": draft.ollama_base_url,
        "PLANSEED_OLLAMA_ALLOW_REMOTE": "1" if allow_remote else "0",
    }
    try:
        enforce_ollama_endpoint_policy(draft.ollama_base_url, environ=probe_env)
    except Exception as exc:
        return OllamaModelsResponse(
            base_url=draft.ollama_base_url,
            reachable=False,
            detail=str(exc),
        )

    cfg = replace(load_ollama_config(environ=probe_env), timeout_s=5.0)
    provider = OllamaProvider(cfg, environ=probe_env, skip_endpoint_policy=True)
    try:
        if not provider.is_available():
            return OllamaModelsResponse(
                base_url=draft.ollama_base_url,
                reachable=False,
                detail=f"无法连接 Ollama（{draft.ollama_base_url}）",
            )
        try:
            models = list(provider.list_models())
        except (OllamaConnectionError, OllamaError) as exc:
            return OllamaModelsResponse(
                base_url=draft.ollama_base_url,
                reachable=False,
                detail=str(exc),
            )
        return OllamaModelsResponse(
            base_url=draft.ollama_base_url,
            models=models,
            reachable=True,
        )
    finally:
        provider.close()


@router.get("/api/settings")
def get_settings() -> SettingsResponse:
    """返回当前有效设置（含 env 覆盖标记）。"""
    return read_effective_settings()


@router.put("/api/settings")
def put_settings(body: SettingsUpdateBody) -> SettingsUpdateResponse:
    """
    保存设置到 ~/.planseed/settings.json，写入 os.environ，
    并重置共享 LLM Provider（下次解析时懒加载）。
    """
    settings = AppSettings(llm=body.llm)
    save_persisted_settings(settings)
    apply_settings_to_environ(settings)
    reset_shared_requirement_provider()

    effective = read_effective_settings()
    health = probe_llm_health().to_dict()
    return SettingsUpdateResponse(settings=effective, llm_health=health)


@router.get("/api/settings/ollama/models")
def list_ollama_models(
    base_url: str | None = Query(default=None, description="探测用 Ollama 根 URL"),
    allow_remote: bool = Query(
        default=False,
        description="是否允许非 loopback（与保存设置一致）",
    ),
) -> OllamaModelsResponse:
    """列出指定 Ollama 实例已安装模型（供设置面板下拉）。"""
    if base_url is None:
        effective = read_effective_settings()
        base_url = effective.llm.ollama_base_url
        allow_remote = effective.llm.ollama_allow_remote
    return _probe_models_at(base_url, allow_remote=allow_remote)

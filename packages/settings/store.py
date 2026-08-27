"""设置读写：~/.planseed/settings.json ↔ os.environ。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from packages.llm.factory import resolve_provider_kind
from packages.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_S,
)
from packages.settings.models import AppSettings, LlmSettings, SettingsResponse

_LLM_ENV_KEYS: dict[str, str] = {
    "provider": "PLANSEED_LLM_PROVIDER",
    "ollama_base_url": "PLANSEED_OLLAMA_BASE_URL",
    "ollama_model": "PLANSEED_OLLAMA_MODEL",
    "ollama_timeout_s": "PLANSEED_OLLAMA_TIMEOUT",
    "ollama_allow_remote": "PLANSEED_OLLAMA_ALLOW_REMOTE",
}


def default_settings_path() -> Path:
    env = os.environ.get("PLANSEED_SETTINGS")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".planseed" / "settings.json"


def _truthy(raw: str | None) -> bool:
    return (raw or "0").strip().lower() in ("1", "true", "yes", "on")


def _read_llm_from_environ(environ: dict[str, str]) -> LlmSettings:
    timeout_raw = environ.get("PLANSEED_OLLAMA_TIMEOUT", str(DEFAULT_OLLAMA_TIMEOUT_S))
    try:
        timeout_s = float(timeout_raw)
    except ValueError:
        timeout_s = DEFAULT_OLLAMA_TIMEOUT_S
    return LlmSettings(
        provider=resolve_provider_kind(environ=environ),
        ollama_base_url=environ.get("PLANSEED_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        ollama_model=environ.get("PLANSEED_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        ollama_timeout_s=timeout_s,
        ollama_allow_remote=_truthy(environ.get("PLANSEED_OLLAMA_ALLOW_REMOTE")),
    )


def _llm_env_overrides(environ: dict[str, str]) -> dict[str, bool]:
    return {field: _LLM_ENV_KEYS[field] in environ for field in _LLM_ENV_KEYS}


def read_effective_settings(
    *,
    environ: dict[str, str] | None = None,
    settings_path: Path | None = None,
) -> SettingsResponse:
    """读取当前进程有效配置（env 优先于文件默认值）。"""
    env = environ if environ is not None else os.environ
    path = settings_path if settings_path is not None else default_settings_path()
    persisted = load_persisted_settings(path=path)
    return SettingsResponse(
        llm=_read_llm_from_environ(env),
        persisted=persisted is not None,
        settings_path=str(path),
        env_overrides=_llm_env_overrides(env),
    )


def load_persisted_settings(*, path: Path | None = None) -> AppSettings | None:
    target = path if path is not None else default_settings_path()
    if not target.is_file():
        return None
    try:
        raw: dict[str, Any] = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return AppSettings.model_validate(raw)


def save_persisted_settings(
    settings: AppSettings,
    *,
    path: Path | None = None,
) -> Path:
    target = path if path is not None else default_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = settings.model_dump(mode="json")
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def apply_settings_to_environ(
    settings: AppSettings,
    *,
    environ: dict[str, str] | None = None,
) -> None:
    """将设置写入环境变量（供 factory / health 读取）。"""
    env = environ if environ is not None else os.environ
    llm = settings.llm
    env["PLANSEED_LLM_PROVIDER"] = llm.provider
    env["PLANSEED_OLLAMA_BASE_URL"] = llm.ollama_base_url
    env["PLANSEED_OLLAMA_MODEL"] = llm.ollama_model
    env["PLANSEED_OLLAMA_TIMEOUT"] = str(llm.ollama_timeout_s)
    env["PLANSEED_OLLAMA_ALLOW_REMOTE"] = "1" if llm.ollama_allow_remote else "0"


def bootstrap_settings(*, path: Path | None = None) -> SettingsResponse:
    """
    引擎启动时调用：若存在 settings.json 则加载并写入 os.environ。

    进程启动前已存在的 PLANSEED_* 环境变量不会被文件覆盖。
    """
    target = path if path is not None else default_settings_path()
    persisted = load_persisted_settings(path=target)
    if persisted is not None:
        env = os.environ
        file_llm = persisted.llm
        if "PLANSEED_LLM_PROVIDER" not in env:
            env["PLANSEED_LLM_PROVIDER"] = file_llm.provider
        if "PLANSEED_OLLAMA_BASE_URL" not in env:
            env["PLANSEED_OLLAMA_BASE_URL"] = file_llm.ollama_base_url
        if "PLANSEED_OLLAMA_MODEL" not in env:
            env["PLANSEED_OLLAMA_MODEL"] = file_llm.ollama_model
        if "PLANSEED_OLLAMA_TIMEOUT" not in env:
            env["PLANSEED_OLLAMA_TIMEOUT"] = str(file_llm.ollama_timeout_s)
        if "PLANSEED_OLLAMA_ALLOW_REMOTE" not in env:
            env["PLANSEED_OLLAMA_ALLOW_REMOTE"] = (
                "1" if file_llm.ollama_allow_remote else "0"
            )
    return read_effective_settings(settings_path=target)

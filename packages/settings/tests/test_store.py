"""settings.json 读写与环境变量同步。"""

from __future__ import annotations

import json
import os

import pytest
from packages.settings.models import AppSettings, LlmSettings
from packages.settings.store import (
    apply_settings_to_environ,
    bootstrap_settings,
    load_persisted_settings,
    read_effective_settings,
    save_persisted_settings,
)


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = AppSettings(
        llm=LlmSettings(
            provider="ollama",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="llama3.2:3b",
            ollama_timeout_s=90,
            ollama_allow_remote=True,
        )
    )
    save_persisted_settings(settings, path=path)
    loaded = load_persisted_settings(path=path)
    assert loaded == settings


def test_bootstrap_applies_file_when_env_missing(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    payload = {
        "version": 1,
        "llm": {
            "provider": "ollama",
            "ollama_base_url": "http://127.0.0.1:11434",
            "ollama_model": "custom:7b",
            "ollama_timeout_s": 60,
            "ollama_allow_remote": False,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.delenv("PLANSEED_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("PLANSEED_LLM_PROVIDER", raising=False)

    effective = bootstrap_settings(path=path)
    assert effective.llm.ollama_model == "custom:7b"
    assert os.environ["PLANSEED_OLLAMA_MODEL"] == "custom:7b"


def test_bootstrap_does_not_override_existing_env(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    save_persisted_settings(
        AppSettings(llm=LlmSettings(ollama_model="from-file:7b")),
        path=path,
    )
    monkeypatch.setenv("PLANSEED_OLLAMA_MODEL", "from-env:7b")

    effective = bootstrap_settings(path=path)
    assert effective.llm.ollama_model == "from-env:7b"
    assert effective.env_overrides["ollama_model"] is True


def test_apply_settings_to_environ():
    env: dict[str, str] = {}
    settings = AppSettings(
        llm=LlmSettings(
            provider="mock",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="qwen2.5:7b",
            ollama_timeout_s=45,
            ollama_allow_remote=True,
        )
    )
    apply_settings_to_environ(settings, environ=env)
    assert env["PLANSEED_LLM_PROVIDER"] == "mock"
    assert env["PLANSEED_OLLAMA_TIMEOUT"] == "45"
    assert env["PLANSEED_OLLAMA_ALLOW_REMOTE"] == "1"


def test_read_effective_settings_marks_env_overrides(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    save_persisted_settings(AppSettings(), path=path)
    monkeypatch.setenv("PLANSEED_OLLAMA_MODEL", "env-model")

    resp = read_effective_settings(settings_path=path)
    assert resp.llm.ollama_model == "env-model"
    assert resp.env_overrides["ollama_model"] is True
    assert resp.persisted is True


def test_invalid_base_url_rejected():
    with pytest.raises(ValueError, match="http"):
        LlmSettings(ollama_base_url="localhost:11434")

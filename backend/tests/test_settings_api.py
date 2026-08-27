"""Settings API — GET/PUT /api/settings。"""

from __future__ import annotations

import json

from backend.main import create_app
from fastapi.testclient import TestClient
from packages.llm.runtime import reset_shared_requirement_provider


def test_get_settings_defaults(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("PLANSEED_SETTINGS", str(path))
    monkeypatch.delenv("PLANSEED_OLLAMA_MODEL", raising=False)
    reset_shared_requirement_provider()

    client = TestClient(create_app())
    r = client.get("/api/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm"]["provider"] == "ollama"
    assert body["llm"]["ollama_model"] == "qwen2.5:7b"
    assert body["persisted"] is False


def test_put_settings_persists_and_applies(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("PLANSEED_SETTINGS", str(path))
    reset_shared_requirement_provider()

    client = TestClient(create_app())
    payload = {
        "llm": {
            "provider": "mock",
            "ollama_base_url": "http://127.0.0.1:11434",
            "ollama_model": "test-model:7b",
            "ollama_timeout_s": 80,
            "ollama_allow_remote": False,
        }
    }
    r = client.put("/api/settings", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["settings"]["llm"]["provider"] == "mock"
    assert body["settings"]["persisted"] is True
    assert body["llm_health"]["provider"] == "mock"

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["llm"]["ollama_model"] == "test-model:7b"

    r2 = client.get("/api/settings")
    assert r2.json()["llm"]["provider"] == "mock"


def test_put_settings_validation_error(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("PLANSEED_SETTINGS", str(path))
    reset_shared_requirement_provider()

    client = TestClient(create_app())
    r = client.put(
        "/api/settings",
        json={"llm": {"ollama_base_url": "not-a-url", "ollama_model": ""}},
    )
    assert r.status_code == 422


def test_list_ollama_models_mock_unreachable(monkeypatch):
    monkeypatch.setenv("PLANSEED_LLM_PROVIDER", "mock")
    reset_shared_requirement_provider()
    client = TestClient(create_app())
    r = client.get(
        "/api/settings/ollama/models",
        params={"base_url": "http://127.0.0.1:59999"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reachable"] is False

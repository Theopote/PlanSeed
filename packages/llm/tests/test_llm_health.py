"""LLM health 探测与 /api/llm/status。"""

from __future__ import annotations

import httpx
from backend.main import create_app
from fastapi.testclient import TestClient
from packages.llm.health import LlmHealthState, probe_llm_health
from packages.llm.ollama import OllamaConfig, OllamaProvider
from packages.llm.runtime import reset_shared_requirement_provider


def test_probe_mock_ready(monkeypatch):
    monkeypatch.setenv("PLANSEED_LLM_PROVIDER", "mock")
    status = probe_llm_health()
    assert status.state == LlmHealthState.MODEL_READY
    assert status.provider == "mock"


def test_probe_model_missing():
    def tags(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "other:1b"}]})

    client = httpx.Client(transport=httpx.MockTransport(tags))
    provider = OllamaProvider(
        OllamaConfig(base_url="http://t", model="qwen2.5:7b"),
        client=client,
    )
    status = probe_llm_health(
        environ={
            "PLANSEED_LLM_PROVIDER": "ollama",
            "PLANSEED_OLLAMA_MODEL": "qwen2.5:7b",
        },
        provider=provider,
    )
    assert status.state == LlmHealthState.MODEL_MISSING
    assert "qwen2.5:7b" in (status.detail or "")
    assert "other:1b" in status.installed_models


def test_probe_model_ready():
    def tags(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    client = httpx.Client(transport=httpx.MockTransport(tags))
    provider = OllamaProvider(
        OllamaConfig(base_url="http://t", model="qwen2.5:7b"),
        client=client,
    )
    status = probe_llm_health(
        environ={
            "PLANSEED_LLM_PROVIDER": "ollama",
            "PLANSEED_OLLAMA_MODEL": "qwen2.5:7b",
        },
        provider=provider,
    )
    assert status.state == LlmHealthState.MODEL_READY


def test_probe_unavailable():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(boom))
    provider = OllamaProvider(
        OllamaConfig(base_url="http://t", model="qwen2.5:7b"),
        client=client,
    )
    status = probe_llm_health(
        environ={"PLANSEED_LLM_PROVIDER": "ollama"},
        provider=provider,
    )
    assert status.state == LlmHealthState.LLM_UNAVAILABLE


def test_llm_status_api_mock(monkeypatch):
    monkeypatch.setenv("PLANSEED_LLM_PROVIDER", "mock")
    reset_shared_requirement_provider()
    try:
        client = TestClient(create_app())
        r = client.get("/api/llm/status")
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "ModelReady"
        assert body["provider"] == "mock"
        assert "model" in body
        assert "installed_models" in body
    finally:
        reset_shared_requirement_provider()

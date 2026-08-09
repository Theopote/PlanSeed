"""Phase 6.1 — OllamaProvider（MockTransport，不依赖本机 Ollama）。"""

from __future__ import annotations

import json

import httpx
import pytest

from packages.llm.factory import (
    create_llm_provider,
    load_ollama_config,
    resolve_provider_kind,
)
from packages.llm.ollama import (
    OllamaConfig,
    OllamaConnectionError,
    OllamaHTTPError,
    OllamaProvider,
    OllamaResponseError,
)


def _chat_handler(content: str, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content.decode())
        assert body["stream"] is False
        assert body.get("format") == "json"
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        return httpx.Response(
            status,
            json={
                "model": body["model"],
                "message": {"role": "assistant", "content": content},
                "done": True,
            },
        )

    return handler


def test_complete_json_success():
    draft = {
        "known": {"floor_count": 2, "household": {"bedrooms": 3}},
        "assumptions": [],
        "unknowns": [{"key": "site.width", "description": "未给"}],
    }
    transport = httpx.MockTransport(_chat_handler(json.dumps(draft)))
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:11434")
    provider = OllamaProvider(
        OllamaConfig(base_url="http://127.0.0.1:11434", model="test-model"),
        client=client,
    )
    out = provider.complete_json(system="sys", user="两层三卧")
    assert out["known"]["floor_count"] == 2
    assert out["unknowns"][0]["key"] == "site.width"


def test_strips_markdown_fence():
    inner = {"known": {"floor_count": 1}, "assumptions": [], "unknowns": []}
    fenced = "```json\n" + json.dumps(inner) + "\n```"
    transport = httpx.MockTransport(_chat_handler(fenced))
    client = httpx.Client(transport=transport)
    provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"), client=client)
    out = provider.complete_json(system="s", user="u")
    assert out["known"]["floor_count"] == 1


def test_http_error():
    transport = httpx.MockTransport(_chat_handler("{}", status=500))
    client = httpx.Client(transport=transport)
    provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"), client=client)
    with pytest.raises(OllamaHTTPError) as ei:
        provider.complete_json(system="s", user="u")
    assert ei.value.status_code == 500


def test_connection_error():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(boom))
    provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"), client=client)
    with pytest.raises(OllamaConnectionError):
        provider.complete_json(system="s", user="u")


def test_invalid_json_content():
    transport = httpx.MockTransport(_chat_handler("not-json{"))
    client = httpx.Client(transport=transport)
    provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"), client=client)
    with pytest.raises(OllamaResponseError):
        provider.complete_json(system="s", user="u")


def test_non_object_json():
    transport = httpx.MockTransport(_chat_handler("[1,2,3]"))
    client = httpx.Client(transport=transport)
    provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"), client=client)
    with pytest.raises(OllamaResponseError):
        provider.complete_json(system="s", user="u")


def test_is_available():
    def tags_ok(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    client = httpx.Client(transport=httpx.MockTransport(tags_ok))
    provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"), client=client)
    assert provider.is_available() is True


def test_is_model_available_exact_and_latest_alias():
    from packages.llm.ollama import model_name_matches

    assert model_name_matches("qwen2.5:7b", "qwen2.5:7b")
    assert model_name_matches("qwen2.5:latest", "qwen2.5")
    assert not model_name_matches("llama3:8b", "qwen2.5:7b")

    def tags(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "llama3:8b"},
                    {"name": "qwen2.5:7b"},
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(tags))
    provider = OllamaProvider(
        OllamaConfig(base_url="http://127.0.0.1:11434", model="qwen2.5:7b"),
        client=client,
    )
    assert provider.is_model_available() is True
    assert provider.is_model_available("llama3:8b") is True
    assert provider.is_model_available("missing:1b") is False
    assert provider.list_models() == ["llama3:8b", "qwen2.5:7b"]


def test_is_model_available_server_down():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(boom))
    provider = OllamaProvider(
        OllamaConfig(base_url="http://127.0.0.1:11434", model="qwen2.5:7b"),
        client=client,
    )
    assert provider.is_available() is False
    assert provider.is_model_available() is False


def test_factory_load_config_and_mock():
    cfg = load_ollama_config(
        environ={
            "PLANSEED_OLLAMA_BASE_URL": "http://127.0.0.1:9999",
            "PLANSEED_OLLAMA_MODEL": "tiny",
            "PLANSEED_OLLAMA_TIMEOUT": "30",
        }
    )
    assert cfg.base_url == "http://127.0.0.1:9999"
    assert cfg.model == "tiny"
    assert cfg.timeout_s == 30.0

    assert resolve_provider_kind(environ={"PLANSEED_LLM_PROVIDER": "mock"}) == "mock"

    mock = create_llm_provider(
        "mock",
        mock_responses=[{"known": {"floor_count": 1}, "assumptions": [], "unknowns": []}],
    )
    data = mock.complete_json(system="s", user="u")
    assert data["known"]["floor_count"] == 1


def test_factory_ollama_uses_injected_client():
    draft = {"known": {}, "assumptions": [], "unknowns": []}
    transport = httpx.MockTransport(_chat_handler(json.dumps(draft)))
    client = httpx.Client(transport=transport)
    provider = create_llm_provider(
        "ollama",
        ollama_config=OllamaConfig(base_url="http://127.0.0.1:11434", model="m"),
        ollama_client=client,
    )
    assert isinstance(provider, OllamaProvider)
    assert provider.complete_json(system="s", user="u") == draft

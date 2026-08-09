"""Phase 6.2 — StructuredRequirementParser。"""

from __future__ import annotations

import httpx
import pytest

from packages.llm import (
    LLMIngestError,
    MockLLMProvider,
    StructuredRequirementParser,
    create_requirement_llm_provider,
    draft_json_schema,
    parse_requirement_text,
)
from packages.llm.ollama import OllamaProvider
from packages.llm.parser import build_user_prompt
from packages.schema.llm_contract import LLMRequirementDraft


def _sample_draft(**overrides):
    base = {
        "known": {
            "floor_count": 2,
            "household": {"bedrooms": 3},
            "preferences": {"prefer_south_facing_living": True},
            "spaces": [
                {
                    "id": "living",
                    "name": "客厅",
                    "category": "public",
                    "floor_preference": ["F1"],
                }
            ],
        },
        "assumptions": [
            {"key": "bathrooms", "value": 2, "reason": "住宅常见默认"}
        ],
        "unknowns": [{"key": "site.width", "description": "未给场地宽度"}],
    }
    base.update(overrides)
    return base


def test_draft_json_schema_shape():
    schema = draft_json_schema()
    assert schema.get("type") == "object" or "$defs" in schema or "properties" in schema
    props = schema.get("properties") or {}
    # Pydantic 顶层或 $ref；至少能从 model 生成
    assert "known" in props or "$defs" in schema
    # round-trip：schema 来自同一模型
    assert LLMRequirementDraft.model_json_schema()["title"] == schema.get("title")


def test_build_user_prompt_rejects_blank():
    with pytest.raises(LLMIngestError):
        build_user_prompt("   ")


def test_parse_requirement_text_happy_path():
    provider = MockLLMProvider([_sample_draft()])
    result = parse_requirement_text("两层三卧，客厅朝南", provider=provider)
    assert result.spec.floor_count == 2
    assert result.spec.household.bedrooms == 3
    assert result.spec.raw_text == "两层三卧，客厅朝南"
    assert result.draft.known.floor_count == 2
    assert result.raw["known"]["floor_count"] == 2
    assert len(result.spec.assumptions) == 1
    # enrich 对未提供场地补列 site.depth（mock 只声明了 site.width）
    unk = {u.key for u in result.spec.unknowns}
    assert unk == {"site.width", "site.depth"}


def test_parser_passes_system_and_user_to_provider():
    seen: dict[str, str] = {}

    def capture(system: str, user: str):
        seen["system"] = system
        seen["user"] = user
        return _sample_draft()

    provider = MockLLMProvider(capture)
    StructuredRequirementParser(provider).parse("小两居")
    assert "禁止" in seen["system"] or "几何" in seen["system"]
    assert "小两居" in seen["user"]
    assert "LLMRequirementDraft" in seen["user"]


def test_parse_rejects_geometry_from_provider():
    provider = MockLLMProvider(
        [
            {
                "known": {
                    "spaces": [{"name": "客厅", "x": 1.0, "y": 2.0}],
                },
                "assumptions": [],
                "unknowns": [],
            }
        ]
    )
    with pytest.raises(Exception) as ei:
        parse_requirement_text("带坐标的坏输出", provider=provider)
    assert "几何" in str(ei.value) or "x" in str(ei.value).lower()


def test_parse_rejects_semantic():
    provider = MockLLMProvider(
        [
            {
                "known": {
                    "floor_count": 1,
                    "spaces": [{"name": "书房", "floor_preference": ["F2"]}],
                },
                "assumptions": [],
                "unknowns": [],
            }
        ]
    )
    with pytest.raises(LLMIngestError):
        parse_requirement_text("一层却要二楼书房", provider=provider)


def test_create_requirement_llm_provider_mock_and_schema_ollama():
    mock = create_requirement_llm_provider(
        environ={"PLANSEED_LLM_PROVIDER": "mock"},
        mock_responses=[_sample_draft()],
    )
    assert parse_requirement_text("x", provider=mock).spec.floor_count == 2

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content.decode())
        captured["format"] = body.get("format")
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(_sample_draft()),
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ollama = create_requirement_llm_provider(
        environ={"PLANSEED_LLM_PROVIDER": "ollama"},
        ollama_client=client,
    )
    assert isinstance(ollama, OllamaProvider)
    ollama.complete_json(system="s", user="u")
    assert isinstance(captured["format"], dict)
    assert captured["format"] == draft_json_schema()

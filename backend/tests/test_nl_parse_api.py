"""Phase 6.5 — POST /api/requirements/parse。"""

from __future__ import annotations

from backend.main import create_app
from backend.services import nl_parse
from fastapi.testclient import TestClient
from packages.llm import MockLLMProvider


def _ok_draft():
    return {
        "known": {
            "floor_count": 2,
            "site": {"width": 11, "depth": 13},
            "household": {"bedrooms": 3, "bathrooms": 2},
            "preferences": {"prefer_south_facing_living": True},
            "spaces": [
                {
                    "id": "living",
                    "name": "客厅",
                    "category": "public",
                    "target_area": 24,
                    "floor_preference": ["F1"],
                }
            ],
        },
        "assumptions": [
            {"key": "bathrooms", "value": 2, "reason": "住宅常见默认"}
        ],
        "unknowns": [{"key": "site.entrance_edge", "description": "未说明入口"}],
    }


def test_parse_nl_happy(monkeypatch):
    monkeypatch.setenv("PLANSEED_LLM_PROVIDER", "mock")
    nl_parse.set_nl_provider_factory(
        lambda: MockLLMProvider([_ok_draft()])
    )
    try:
        client = TestClient(create_app())
        r = client.post(
            "/api/requirements/parse",
            json={"text": "两层三卧，客厅朝南，地块约 11×13"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["requirement_spec"]["floor_count"] == 2
        assert body["requirement_spec"]["household"]["bedrooms"] == 3
        assert body["requirement_spec"]["raw_text"]
        assert body["attempts"] == 1
        assert body["provider"] == "mock"
        assert len(body["requirement_spec"]["assumptions"]) == 1
        assert len(body["requirement_spec"]["unknowns"]) == 1
    finally:
        nl_parse.set_nl_provider_factory(None)


def test_parse_nl_repair_then_ok(monkeypatch):
    bad = {
        "known": {
            "floor_count": 1,
            "spaces": [{"name": "书房", "floor_preference": ["F2"]}],
        },
        "assumptions": [],
        "unknowns": [],
    }
    good = {
        "known": {
            "floor_count": 1,
            "site": {"width": 10, "depth": 12},
            "household": {"bedrooms": 2},
            "spaces": [{"name": "书房", "floor_preference": ["F1"]}],
        },
        "assumptions": [],
        "unknowns": [],
    }
    nl_parse.set_nl_provider_factory(lambda: MockLLMProvider([bad, good]))
    try:
        client = TestClient(create_app())
        r = client.post(
            "/api/requirements/parse",
            json={"text": "一层带书房", "max_repairs": 2},
        )
        assert r.status_code == 200, r.text
        assert r.json()["attempts"] == 2
        assert r.json()["requirement_spec"]["spaces"][0]["floor_preference"] == [
            "F1"
        ]
    finally:
        nl_parse.set_nl_provider_factory(None)


def test_parse_nl_exhausted(monkeypatch):
    bad = {
        "known": {
            "floor_count": 1,
            "spaces": [{"name": "书房", "floor_preference": ["F3"]}],
        },
        "assumptions": [],
        "unknowns": [],
    }
    nl_parse.set_nl_provider_factory(lambda: MockLLMProvider([bad, bad, bad]))
    try:
        client = TestClient(create_app())
        r = client.post(
            "/api/requirements/parse",
            json={"text": "坏", "max_repairs": 2},
        )
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["attempts"] == 3
    finally:
        nl_parse.set_nl_provider_factory(None)


def test_parse_nl_empty_text():
    client = TestClient(create_app())
    r = client.post("/api/requirements/parse", json={"text": "  "})
    assert r.status_code == 422

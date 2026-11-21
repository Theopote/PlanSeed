"""Copilot API 冒烟。"""

from __future__ import annotations

from backend.main import create_app
from fastapi.testclient import TestClient


def test_strategies_and_intent_parse():
    client = TestClient(create_app())
    r = client.get("/api/copilot/strategies")
    assert r.status_code == 200
    assert len(r.json()) == 3

    p = client.post(
        "/api/copilot/intent/parse",
        json={"text": "保持客厅不变，主卧大一点，避免穿过卧室"},
    )
    assert p.status_code == 200
    body = p.json()
    assert "preserve" in body
    assert body["changes"]

    prev = client.post(
        "/api/copilot/intent/preview",
        json={"patch": body, "use_benchmark": True},
    )
    assert prev.status_code == 200
    assert "mutable_rooms" in prev.json()


def test_conversation_roundtrip():
    client = TestClient(create_app())
    pid = "test-conv-1"
    r = client.get(f"/api/copilot/conversation/{pid}")
    assert r.status_code == 200
    assert r.json()["project_id"] == pid

    a = client.post(
        f"/api/copilot/conversation/{pid}/messages",
        json={
            "project_id": pid,
            "role": "user",
            "content": "先选家庭交流优先",
            "meta": {},
        },
    )
    assert a.status_code == 200
    assert len(a.json()["messages"]) == 1

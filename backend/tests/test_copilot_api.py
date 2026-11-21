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


def test_strategy_generate_tags_candidates():
    client = TestClient(create_app())
    r = client.post(
        "/api/copilot/strategy/generate",
        json={
            "strategy_id": "family_core",
            "use_benchmark": True,
            "candidate_count": 4,
            "return_top_k": 2,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["candidates"]
    # metrics 经 serialize 可能在 candidate.metrics
    m0 = body["candidates"][0].get("metrics") or {}
    assert m0.get("topology_strategy_id") == "family_core"
    assert m0.get("topology_strategy_label") == "家庭交流优先"


def test_intent_apply_partial_regen():
    client = TestClient(create_app())
    gen = client.post(
        "/api/generate",
        json={"use_benchmark": True, "candidate_count": 4, "return_top_k": 1},
    )
    assert gen.status_code == 200, gen.text
    cand = gen.json()["candidates"][0]
    placements = cand.get("placements") or []
    assert placements

    parsed = client.post(
        "/api/copilot/intent/parse",
        json={"text": "保持客厅不变，主卧大一点"},
    ).json()

    applied = client.post(
        "/api/copilot/intent/apply",
        json={
            "patch": parsed,
            "use_benchmark": True,
            "base_placements": [
                {
                    "room_id": p["room_id"],
                    "floor_id": p["floor_id"],
                    "x": p["x"],
                    "y": p["y"],
                    "width": p["width"],
                    "depth": p["depth"],
                    "area": p.get("area", p["width"] * p["depth"]),
                }
                for p in placements
                if not str(p["room_id"]).startswith("stair-")
            ][:20],
            "candidate_count": 4,
            "return_top_k": 2,
            "base_seed": 10,
        },
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["generated"] >= 1
    # 局部锁可能使本轮 valid=0；仍须返回结构化响应
    assert "candidates" in body
    assert "program_summary" in body

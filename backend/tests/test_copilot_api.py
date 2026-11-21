"""Copilot API 冒烟。"""

from __future__ import annotations

from pathlib import Path

import pytest
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
    data = prev.json()
    assert data["mutable_rooms"]
    # 顶层 locked_rooms 须为实际锁定集合（非 scope 空列表）
    assert data["locked_rooms"]
    assert "r1" in data["locked_rooms"] or any(
        "客厅" in str(x) or x.startswith("r") for x in data["locked_rooms"]
    )


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
    gen_body = gen.json()
    cand = gen_body["candidates"][0]
    placements = cand.get("placements") or []
    assert placements
    base_spec = gen_body["requirement_spec"]
    assert base_spec

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
    # P0：写回后的 RequirementSpec 须反映主卧面积增大
    out_spec = body["requirement_spec"]
    assert out_spec is not None
    prog_rooms = {r["id"]: r for r in body["program_summary"]["rooms"]}
    master = next(
        (r for r in prog_rooms.values() if "主卧" in (r.get("name") or "") or "master" in r["id"]),
        None,
    )
    if master is not None:
        space = next(
            (
                s
                for s in out_spec["spaces"]
                if s.get("id") == master["id"] or s.get("name") == master.get("name")
            ),
            None,
        )
        assert space is not None
        assert space["target_area"] == master["target_area"]
        base_space = next(
            (
                s
                for s in base_spec["spaces"]
                if s.get("id") == master["id"] or s.get("name") == master.get("name")
            ),
            None,
        )
        if base_space and base_space.get("target_area"):
            assert space["target_area"] > base_space["target_area"]


def test_critique_accepts_candidate_payload_shape():
    """桌面发送扁平 placements + design_score，不得被解析成空 floors。"""
    client = TestClient(create_app())
    gen = client.post(
        "/api/generate",
        json={"use_benchmark": True, "candidate_count": 4, "return_top_k": 1},
    )
    assert gen.status_code == 200, gen.text
    cand = gen.json()["candidates"][0]
    assert cand.get("placements")
    assert "floors" not in cand or not cand.get("floors")

    # 人为植入 finding，验证 Critic 读 evaluation.findings
    score = cand.get("design_score") or {}
    score = {
        **score,
        "findings": [
            {
                "id": "dark_bath",
                "category": "environment",
                "severity": "warning",
                "message": "黑卫",
                "title": "黑卫",
                "room_ids": [],
            }
        ],
    }
    cand = {**cand, "design_score": score}

    r = client.post(
        "/api/copilot/critique",
        json={"use_benchmark": True, "candidate": cand},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    msgs = [x.get("message", "") for x in body.get("should_improve", [])]
    msgs += [x.get("message", "") for x in body.get("must_fix", [])]
    assert any("黑卫" in m for m in msgs)


def test_critique_rejects_empty_geometry():
    client = TestClient(create_app())
    r = client.post(
        "/api/copilot/critique",
        json={
            "use_benchmark": True,
            "candidate": {
                "id": "empty",
                "seed": 0,
                "score": None,
                "label": "X",
                "svg": "",
                "placements": [],
            },
        },
    )
    assert r.status_code == 422


def test_design_conversation_persists_in_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "conv.db"))
    client = TestClient(create_app())
    conv = {
        "project_id": "will-be-overwritten",
        "messages": [
            {
                "id": "m1",
                "role": "user",
                "content": "主卧大一点",
                "created_at": "2026-11-21T00:00:00+00:00",
                "meta": {},
            }
        ],
        "selected_candidate_id": "c1",
        "active_strategy_id": None,
        "applied_patch_ids": [],
        "confirmed_facts": [],
        "locked_room_ids": [],
        "updated_at": "2026-11-21T00:00:00+00:00",
    }
    saved = client.post(
        "/api/projects",
        json={
            "name": "对话宅",
            "payload": {
                "form": {"width": 12, "depth": 15, "floors": 2},
                "program": {"rooms": []},
                "requirement_spec": {"spaces": []},
                "locks": {},
                "candidates": [],
                "design_conversation": conv,
            },
        },
    )
    assert saved.status_code == 200, saved.text
    pid = saved.json()["id"]
    loaded = client.get(f"/api/projects/{pid}")
    assert loaded.status_code == 200
    dc = loaded.json()["payload"].get("design_conversation")
    assert dc is not None
    assert len(dc["messages"]) == 1
    assert dc["messages"][0]["content"] == "主卧大一点"

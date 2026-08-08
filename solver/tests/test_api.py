"""FastAPI generate 端点烟雾测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_generate_benchmark():
    r = client.post(
        "/api/generate",
        json={"use_benchmark": True, "candidate_count": 8, "return_top_k": 3},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["generated"] == 8
    assert len(data["candidates"]) >= 1
    c0 = data["candidates"][0]
    assert c0["label"] == "A"
    assert c0["svg"].lstrip().startswith("<svg")
    assert c0["design_score"] is not None
    assert c0["design_score"]["total_score"] > 0
    assert data["program_summary"]["floor_count"] >= 1


def test_generate_requires_body():
    r = client.post("/api/generate", json={})
    assert r.status_code == 400

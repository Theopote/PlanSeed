"""Phase 4.2：GenerateRequest.base_seed 透传。"""

from __future__ import annotations

from backend.main import create_app
from fastapi.testclient import TestClient


def test_generate_respects_base_seed():
    client = TestClient(create_app())
    r = client.post(
        "/api/generate",
        json={
            "use_benchmark": True,
            "candidate_count": 3,
            "return_top_k": 3,
            "base_seed": 900,
        },
    )
    assert r.status_code == 200
    seeds = [c["seed"] for c in r.json()["candidates"]]
    assert seeds
    assert min(seeds) >= 900
    assert max(seeds) <= 902

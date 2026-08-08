"""POST /api/compare — 比较规则在 Python，不在前端。"""

from __future__ import annotations

from backend.main import create_app
from fastapi.testclient import TestClient
from packages.schema.scoring import DesignScore


def _score(**overrides: float) -> DesignScore:
    base = dict(
        program_score=70,
        spatial_score=70,
        circulation_score=70,
        privacy_score=70,
        environment_score=70,
        technical_score=70,
        robustness_score=70,
        total_score=70,
    )
    base.update(overrides)
    return DesignScore(**base)


def test_compare_api_axis_advantage():
    client = TestClient(create_app())
    a = _score(spatial_score=80, total_score=72)
    b = _score(spatial_score=70, total_score=70)
    r = client.post(
        "/api/compare",
        json={
            "evaluation_a": a.model_dump(mode="json"),
            "evaluation_b": b.model_dump(mode="json"),
            "label_a": "A",
            "label_b": "B",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["label_a"] == "A"
    assert body["label_b"] == "B"
    assert len(body["rows"]) >= 8
    assert any("Spatial" in x or "比例" in x for x in body["advantages_a"])
    spatial = next(row for row in body["rows"] if row["key"] == "spatial_score")
    assert spatial["score_a"] == 80
    assert spatial["score_b"] == 70

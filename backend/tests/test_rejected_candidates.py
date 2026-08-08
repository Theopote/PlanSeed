"""Rejected Candidates API 契约：仅 hard-fail，≠ 未进 Top-K。"""

from __future__ import annotations

from backend.main import create_app
from backend.schemas.api import MAX_REJECTED_SAMPLES
from backend.services.serialization import serialize_rejected
from fastapi.testclient import TestClient
from packages.schema.layout import (
    CandidateValidation,
    LayoutCandidate,
    Violation,
)


def test_serialize_rejected_extracts_hard_messages():
    cand = LayoutCandidate(
        id="candidate-1",
        seed=47,
        floors=[],
        validation=CandidateValidation(
            valid=False,
            hard_violations=[
                Violation(
                    constraint_id="access.unreachable",
                    message="Bedroom 2 unreachable",
                    hard=True,
                ),
                Violation(
                    constraint_id="adjacency.kitchen_dining",
                    message="Required Kitchen–Dining opening unavailable",
                    hard=True,
                ),
            ],
        ),
    )
    payload = serialize_rejected(cand)
    assert payload.seed == 47
    assert payload.reasons == [
        "Bedroom 2 unreachable",
        "Required Kitchen–Dining opening unavailable",
    ]
    assert payload.constraint_ids == [
        "access.unreachable",
        "adjacency.kitchen_dining",
    ]


def test_generate_response_includes_rejected_fields():
    client = TestClient(create_app())
    r = client.post(
        "/api/generate",
        json={
            "use_benchmark": True,
            "candidate_count": 16,
            "return_top_k": 5,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "violation_summary" in body
    assert "rejected_candidates" in body
    assert isinstance(body["violation_summary"], dict)
    assert isinstance(body["rejected_candidates"], list)
    assert body["rejected"] == body["generated"] - body["valid"]
    assert len(body["rejected_candidates"]) <= MAX_REJECTED_SAMPLES
    assert len(body["rejected_candidates"]) <= body["rejected"]

    for item in body["rejected_candidates"]:
        assert "seed" in item
        assert "reasons" in item
        assert "constraint_ids" in item
        assert isinstance(item["reasons"], list)

    if body["rejected"] > 0:
        assert len(body["rejected_candidates"]) >= 1
        assert all(len(x["reasons"]) >= 1 for x in body["rejected_candidates"])
        for key, count in body["violation_summary"].items():
            assert isinstance(key, str) and key
            assert isinstance(count, int) and count >= 1
    else:
        assert body["rejected_candidates"] == []

"""Phase 7.2.3 — DesignReport JSON Final Export 测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.main import create_app
from fastapi.testclient import TestClient
from packages.schema.report import REPORT_SCHEMA_VERSION
from packages.schema.scoring import DesignScore


def _score() -> dict:
    return DesignScore(
        program_score=80,
        spatial_score=78,
        circulation_score=75,
        privacy_score=80,
        environment_score=70,
        technical_score=76,
        robustness_score=74,
        total_score=76.0,
        findings=[],
    ).model_dump(mode="json")


def _svg(label: str = "F1") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
        f'<rect width="100" height="80" fill="#eee"/>'
        f"<text>{label}</text></svg>"
    )


def _candidate(**overrides) -> dict:
    base = {
        "id": "c-a",
        "seed": 42,
        "score": 76.0,
        "label": "A",
        "svg": _svg("ALL"),
        "floor_svgs": {"F1": _svg("F1"), "F2": _svg("F2")},
        "design_score": _score(),
        "provenance": {
            "solver_version": "test-s",
            "generator_version": "test-g",
            "evaluation_version": "test-e",
        },
        "revision_status": "generated",
        "revision_id": "c-a:gen:deadbeef",
        "placements": [
            {
                "room_id": "r1",
                "floor_id": "F1",
                "x": 0,
                "y": 0,
                "width": 4.0,
                "depth": 3.5,
                "area": 14.0,
            }
        ],
        "validation": {"valid": True, "hard_violations": [], "soft_violations": []},
    }
    base.update(overrides)
    return base


def _payload(candidate: dict | None = None) -> dict:
    return {
        "form": {"bedrooms": 3},
        "program": {
            "rooms": [
                {"id": "r1", "name": "客厅", "category": "living", "target_area": 20}
            ]
        },
        "requirement_spec": {
            "floor_count": 2,
            "household": {"bedrooms": 3, "bathrooms": 2, "has_garage": True},
            "site": {"width": 11, "depth": 13},
            "spaces": [],
            "assumptions": [
                {"key": "a1", "value": True, "reason": "缺省", "source": "system"}
            ],
            "unknowns": [{"key": "u1", "description": "未知朝向", "priority": "low"}],
        },
        "candidates": [candidate or _candidate()],
        "selected_id": "c-a",
        "locks": {"rooms": [], "stair": None, "zones": []},
    }


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "exports-json.db"))
    return TestClient(create_app())


def _save(client: TestClient, payload: dict | None = None, name: str = "JsonExport") -> str:
    r = client.post(
        "/api/projects",
        json={"name": name, "payload": payload or _payload()},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_report_json_export_final_revision(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/report-json",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    assert "DesignReport" in r.headers.get("content-disposition", "")
    assert r.headers.get("X-PlanSeed-Report-Schema-Version") == REPORT_SCHEMA_VERSION
    data = json.loads(r.content.decode("utf-8"))
    assert data["report_schema_version"] == REPORT_SCHEMA_VERSION
    assert data["source_revision_id"] == "c-a:gen:deadbeef"
    assert data["candidate"]["candidate_id"] == "c-a"
    assert data["room_schedule"][0]["area"] == 14.0
    assert data["evaluation"]["design_score"]["total_score"] == 76.0
    assert data["provenance"]["export_mode"] == "final"
    assert any("两层" in s or "2" in s for s in data["requirement"]["key_intents"]) or data[
        "requirement"
    ]["floor_count"] == 2


def test_report_json_not_project_snapshot(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/report-json",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "include_svg": False,
        },
    )
    assert r.status_code == 200, r.text
    data = json.loads(r.content.decode("utf-8"))
    for forbidden in ("candidates", "form", "locks", "selected_id", "program"):
        assert forbidden not in data
    assert "report_schema_version" in data
    assert "room_schedule" in data
    assert "findings" in data
    assert "assumptions" in data
    assert "unknowns" in data
    # include_svg=false → 平面元数据在，svg 空
    assert data["floor_plans"]
    assert all(fp.get("svg", "") == "" for fp in data["floor_plans"])


def test_report_json_wrong_revision_rejected(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/report-json",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "wrong",
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "revision_mismatch"


def test_report_json_dirty_candidate_rejected(client: TestClient):
    cand = _candidate(revision_status="dirty")
    pid = _save(client, _payload(cand))
    r = client.post(
        "/api/exports/report-json",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "candidate_requires_revalidation"


def test_report_json_sanitized_svg(client: TestClient):
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        "<script>alert(1)</script>"
        '<rect width="10" height="10"/>'
        "</svg>"
    )
    cand = _candidate(floor_svgs={"F1": dirty}, svg=dirty)
    pid = _save(client, _payload(cand))
    r = client.post(
        "/api/exports/report-json",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "include_svg": True,
        },
    )
    assert r.status_code == 200, r.text
    data = json.loads(r.content.decode("utf-8"))
    joined = " ".join(fp.get("svg", "") for fp in data["floor_plans"]).lower()
    assert "<script" not in joined
    assert "<svg" in joined


def test_report_schema_version_on_model():
    from packages.schema.report import CandidateSummary, DesignReport

    report = DesignReport(
        candidate=CandidateSummary(candidate_id="c1", label="A"),
    )
    assert report.report_schema_version == REPORT_SCHEMA_VERSION
    dumped = report.model_dump(mode="json")
    assert dumped["report_schema_version"] == REPORT_SCHEMA_VERSION

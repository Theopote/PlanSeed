"""Phase 7.2.1 — SVG Final Export 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.main import create_app
from backend.services.export.svg_exporter import sanitize_export_filename
from fastapi.testclient import TestClient
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
        "form": {},
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
        },
        "candidates": [candidate or _candidate()],
        "selected_id": "c-a",
    }


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "exports.db"))
    return TestClient(create_app())


def _save(client: TestClient, payload: dict | None = None, name: str = "导出测") -> str:
    r = client.post(
        "/api/projects",
        json={"name": name, "payload": payload or _payload()},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_svg_export_final_revision(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/svg",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "floor",
            "floor_id": "F1",
        },
    )
    assert r.status_code == 200, r.text
    assert "image/svg+xml" in r.headers["content-type"]
    cd = r.headers.get("content-disposition", "")
    assert "filename*=" in cd
    assert "F1" in cd
    assert b"<svg" in r.content
    assert b"F1" in r.content


def test_svg_export_wrong_revision_rejected(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/svg",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "wrong-rev",
            "scope": "snapshot",
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "revision_mismatch"


def test_svg_export_floor_not_found(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/exports/svg",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "floor",
            "floor_id": "F9",
        },
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "floor_not_found"


def test_svg_export_dirty_candidate_rejected(client: TestClient):
    cand = _candidate(revision_status="dirty")
    pid = _save(client, _payload(cand))
    r = client.post(
        "/api/exports/svg",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "snapshot",
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "candidate_requires_revalidation"


def test_svg_export_sanitized(client: TestClient):
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        "<script>alert(1)</script>"
        '<rect width="10" height="10"/>'
        "</svg>"
    )
    cand = _candidate(floor_svgs={"F1": dirty}, svg=dirty)
    pid = _save(client, _payload(cand))
    r = client.post(
        "/api/exports/svg",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "floor",
            "floor_id": "F1",
        },
    )
    assert r.status_code == 200, r.text
    assert b"<script" not in r.content.lower()
    assert b"<svg" in r.content


def test_svg_export_content_type(client: TestClient):
    pid = _save(client)
    snap = client.post(
        "/api/exports/svg",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "snapshot",
        },
    )
    assert snap.status_code == 200
    assert snap.headers["content-type"].startswith("image/svg+xml")
    assert "ALL" in snap.headers.get("content-disposition", "")
    assert "filename*=" in snap.headers.get("content-disposition", "")

    z = client.post(
        "/api/exports/svg",
        json={
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:deadbeef",
            "scope": "all_floors",
        },
    )
    assert z.status_code == 200, z.text
    assert z.headers["content-type"] == "application/zip"
    assert z.content[:2] == b"PK"


def test_sanitize_export_filename():
    from backend.services.export.svg_exporter import content_disposition_attachment

    assert ".." not in sanitize_export_filename("../evil/name.svg")
    assert "/" not in sanitize_export_filename("a/b")
    assert sanitize_export_filename("两层住宅").startswith("两")
    cd = content_disposition_attachment("两层住宅_A_F1.svg")
    assert "filename*=UTF-8''" in cd
    assert "两层住宅" not in cd.split(";")[0]  # ASCII filename 段无裸中文
    assert "%E4%B8%A4" in cd or "UTF-8''" in cd

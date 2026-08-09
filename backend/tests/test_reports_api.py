"""Phase 7 — Design Report API / builder 测试。"""

from __future__ import annotations

from backend.main import create_app
from backend.services.report_builder import build_design_report
from backend.services.report_html import render_report_html
from fastapi.testclient import TestClient
from packages.schema.scoring import DesignFinding, DesignScore, FindingSeverity


def _candidate() -> dict:
    score = DesignScore(
        program_score=80,
        spatial_score=78,
        circulation_score=75,
        privacy_score=82,
        environment_score=70,
        technical_score=76,
        robustness_score=74,
        total_score=76.5,
        findings=[
            DesignFinding(
                id="spatial.ok",
                category="spatial",
                severity=FindingSeverity.POSITIVE,
                title="比例尚可",
                message="主要房间比例在可接受范围",
            )
        ],
    )
    return {
        "id": "c-a",
        "seed": 42,
        "score": 76.5,
        "label": "A",
        "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
        '<rect width="100" height="80" fill="#eee"/></svg>',
        "design_score": score.model_dump(mode="json"),
        "provenance": {
            "solver_version": "test-s",
            "generator_version": "test-g",
            "evaluation_version": "test-e",
        },
        "revision_status": "generated",
        "placements": [
            {
                "room_id": "r1",
                "floor_id": "F1",
                "x": 0,
                "y": 0,
                "width": 4.0,
                "depth": 3.5,
                "area": 14.0,
            },
            {
                "room_id": "r2",
                "floor_id": "F1",
                "x": 4,
                "y": 0,
                "width": 3.0,
                "depth": 3.5,
                "area": 10.5,
            },
        ],
    }


def _payload() -> dict:
    return {
        "form": {},
        "program": {
            "rooms": [
                {"id": "r1", "name": "客厅", "category": "living", "target_area": 20},
                {"id": "r2", "name": "厨房", "category": "wet", "target_area": 8},
            ]
        },
        "requirement_spec": {
            "floor_count": 2,
            "household": {"bedrooms": 3, "bathrooms": 2, "has_garage": True},
            "site": {"width": 11, "depth": 13},
            "preferences": {"prefer_south_facing_living": True},
            "relation_intents": [
                {"a": "厨房", "b": "餐厅", "kind": "near"},
            ],
            "assumptions": [],
            "unknowns": [
                {"key": "site.entrance_edge", "description": "入口朝向未定"},
            ],
            "spaces": [],
        },
        "candidates": [_candidate()],
        "selected_id": "c-a",
    }


def test_build_design_report_uses_placement_area():
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=_candidate(),
    )
    assert report.candidate.label == "A"
    assert report.candidate.total_score == 76.5
    assert len(report.room_schedule) == 2
    living = next(r for r in report.room_schedule if r.room_id == "r1")
    assert living.name == "客厅"
    assert living.area == 14.0  # 非前端重算
    assert "Two-story residence" in report.requirement.key_intents
    assert any("south" in x.lower() for x in report.requirement.key_intents)
    assert report.findings and report.findings[0].title == "比例尚可"
    assert any("deterministic solver" in line for line in report.provenance.boundary_lines)


def test_render_report_html_contains_boundary_and_schedule():
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=_candidate(),
    )
    doc = render_report_html(report)
    assert "PlanSeed Design Report" in doc
    assert "客厅" in doc
    assert "14.00" in doc
    assert "AI interpreted design intent" in doc
    assert "<svg" in doc


def test_reports_build_api():
    client = TestClient(create_app())
    r = client.post(
        "/api/reports/build",
        json={
            "project_name": "API Demo",
            "payload": _payload(),
            "candidate_id": "c-a",
            "include_html": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report"]["project"]["project_name"] == "API Demo"
    assert body["report"]["candidate"]["candidate_id"] == "c-a"
    assert body["html"] and "PlanSeed Design Report" in body["html"]


def test_reports_build_requires_source():
    client = TestClient(create_app())
    r = client.post("/api/reports/build", json={"include_html": False})
    assert r.status_code == 422

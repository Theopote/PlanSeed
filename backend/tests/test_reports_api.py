"""Phase 7 — Design Report API / builder / SVG sanitize 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.main import create_app
from backend.services.report_builder import (
    ReportAreaMissingError,
    ReportBuildError,
    build_design_report,
)
from backend.services.report_html import render_report_html
from backend.services.report_svg_sanitize import SvgSanitizeError, sanitize_report_svg
from fastapi.testclient import TestClient
from packages.schema.report_i18n import ReportLocale
from packages.schema.scoring import DesignFinding, DesignScore, FindingSeverity
from pytest import raises


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


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "reports.db"))
    return TestClient(create_app())


def _save_project(client: TestClient, payload: dict | None = None, name: str = "Demo") -> str:
    r = client.post(
        "/api/projects",
        json={"name": name, "payload": payload or _payload()},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_build_design_report_uses_placement_area():
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=_candidate(),
    )
    assert report.candidate.label == "A"
    assert report.candidate.total_score == 76.5
    assert report.status.value == "valid"
    assert report.evaluation.evaluation_fresh is True
    assert report.source_revision_id == "c-a"
    assert len(report.room_schedule) == 2
    living = next(r for r in report.room_schedule if r.room_id == "r1")
    assert living.name == "客厅"
    assert living.area == 14.0
    assert "两层住宅" in report.requirement.key_intents
    assert any("朝南" in x for x in report.requirement.key_intents)
    assert "厨房靠近餐厅" in report.requirement.key_intents
    assert not any(" near " in x or x.endswith(" near") for x in report.requirement.key_intents)
    assert report.findings and report.findings[0].title == "比例尚可"
    assert report.findings_disclaimer is not None
    assert any("确定性求解器" in line for line in report.provenance.boundary_lines)
    assert report.project.locale == ReportLocale.ZH_CN


def test_geometry_origin_labels():
    from backend.services.report_builder import geometry_origin_for_candidate
    from packages.schema.report import GeometryOrigin

    base = _candidate()
    assert geometry_origin_for_candidate(base) == GeometryOrigin.SOLVER_GENERATED

    validated = {**base, "revision_status": "validated", "mutations": [{"id": "m1"}]}
    assert (
        geometry_origin_for_candidate(validated)
        == GeometryOrigin.USER_EDITED_VALIDATED
    )

    stale = {**base, "revision_status": "dirty"}
    assert geometry_origin_for_candidate(stale) == GeometryOrigin.USER_EDITED_STALE

    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=validated,
    )
    assert report.project.geometry_origin == GeometryOrigin.USER_EDITED_VALIDATED
    assert report.project.edited is True
    doc = render_report_html(report)
    assert "用户编辑 · 已验证" in doc
    assert 'lang="zh-CN"' in doc

    stale_report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=stale,
        export_mode="preview",
    )
    assert "用户编辑 · 评价过期" in render_report_html(stale_report)


def test_report_locale_en_us_key_intents():
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=_candidate(),
        locale=ReportLocale.EN_US,
    )
    assert "Two-story residence" in report.requirement.key_intents
    assert "厨房 is near 餐厅" in report.requirement.key_intents
    doc = render_report_html(report)
    assert 'lang="en-US"' in doc
    assert "01 Design Brief" in doc
    assert "02 Plan Snapshot" in doc or "02 Floor Plans" in doc
    assert "03 Space Schedule" in doc


def test_present_relation_intent_covers_kinds():
    from packages.schema.report_i18n import present_relation_intent

    assert present_relation_intent(ReportLocale.ZH_CN, "厨房", "餐厅", "near") == (
        "厨房靠近餐厅"
    )
    assert present_relation_intent(
        ReportLocale.ZH_CN, "客厅", "餐厅", "open_connection"
    ) == "客厅与餐厅开敞连通"
    assert present_relation_intent(
        ReportLocale.ZH_CN, "车库", "门厅", "access"
    ) == "车库可直接进入门厅"
    assert present_relation_intent(
        ReportLocale.ZH_CN, "主卧", "客厅", "separation"
    ) == "主卧与客厅保持距离"
    assert "near" not in present_relation_intent(
        ReportLocale.ZH_CN, "A", "B", "near"
    )


def test_floor_plans_default_to_candidate_snapshot():
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=_candidate(),
    )
    assert len(report.floor_plans) == 1
    assert report.floor_plans[0].floor_id == "all"
    assert "<svg" in report.floor_plans[0].svg


def test_floor_svgs_consumed_without_dom_slicing():
    cand = _candidate()
    cand["floor_svgs"] = {
        "F2": '<svg id="f2"/>',
        "F1": '<svg id="f1"/>',
    }
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=cand,
    )
    assert [b.floor_id for b in report.floor_plans] == ["F1", "F2"]
    assert report.floor_plans[0].svg == '<svg id="f1"/>'


def test_dirty_candidate_marks_stale_evaluation():
    dirty = {**_candidate(), "revision_status": "dirty"}
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=dirty,
    )
    assert report.status.value == "stale_evaluation"
    assert report.evaluation.evaluation_fresh is False


def test_missing_placement_area_raises():
    cand = _candidate()
    del cand["placements"][0]["area"]
    with raises(ReportAreaMissingError) as ei:
        build_design_report(
            project_name="Demo",
            requirement_spec=_payload()["requirement_spec"],
            program=_payload()["program"],
            candidate=cand,
        )
    assert ei.value.room_id == "r1"
    assert ei.value.code == "placement_area_missing"


def test_missing_requirement_spec_raises():
    with raises(ReportBuildError) as ei:
        build_design_report(
            project_name="Demo",
            requirement_spec=None,
            program=_payload()["program"],
            candidate=_candidate(),
        )
    assert ei.value.code == "requirement_spec_missing"


def test_missing_design_score_raises():
    cand = _candidate()
    del cand["design_score"]
    with raises(ReportBuildError) as ei:
        build_design_report(
            project_name="Demo",
            requirement_spec=_payload()["requirement_spec"],
            program=_payload()["program"],
            candidate=cand,
        )
    assert ei.value.code == "design_score_missing"


def test_empty_placements_is_invalid_candidate():
    cand = _candidate()
    cand["placements"] = []
    with raises(ReportBuildError) as ei:
        build_design_report(
            project_name="Demo",
            requirement_spec=_payload()["requirement_spec"],
            program=_payload()["program"],
            candidate=cand,
        )
    assert ei.value.code == "invalid_candidate"


def test_sanitize_strips_script_and_keeps_geometry():
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<script>alert(1)</script>'
        '<rect width="10" height="10" onclick="evil()" fill="#eee"/>'
        '<a href="javascript:alert(1)"><text>x</text></a>'
        '<image href="https://evil.example/x.png"/>'
        "</svg>"
    )
    out = sanitize_report_svg(dirty)
    assert "<script" not in out.lower()
    assert "onclick" not in out.lower()
    assert "javascript:" not in out.lower()
    assert "<image" not in out.lower()
    assert "<a" not in out.lower()
    assert "<rect" in out
    assert 'fill="#eee"' in out or "fill='#eee'" in out or 'fill="#eee"' in out


def test_sanitize_rejects_css_url_external():
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect width="10" height="10" fill="url(https://evil.example/x)"/>'
        "</svg>"
    )
    out = sanitize_report_svg(dirty)
    assert "evil.example" not in out
    assert "<rect" in out


def test_sanitize_rejects_non_svg_root():
    with raises(SvgSanitizeError):
        sanitize_report_svg("<div><svg/></div>")


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
    assert "AI 解释设计意图" in doc or "确定性求解器" in doc
    assert "<svg" in doc
    assert "<script" not in doc.lower()
    assert "设计要点" in doc
    assert "findings-disclaimer" in doc
    assert report.findings_disclaimer in doc


def test_render_report_html_sanitizes_malicious_svg():
    cand = _candidate()
    cand["svg"] = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<script>alert(1)</script><rect width="1" height="1"/></svg>'
    )
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=cand,
    )
    doc = render_report_html(report)
    assert "<script" not in doc.lower()
    assert "<rect" in doc


def test_reports_build_final_api(client: TestClient):
    pid = _save_project(client, name="API Demo")
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "project_name": "API Demo",
            "candidate_id": "c-a",
            "revision_id": "c-a",  # 旧快照无 revision_id → 回退 id
            "include_html": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report"]["project"]["project_name"] == "API Demo"
    assert body["report"]["candidate"]["candidate_id"] == "c-a"
    assert body["report"]["source_revision_id"] == "c-a"
    assert body["report"]["provenance"]["export_mode"] == "final"
    assert body["html"] and "PlanSeed Design Report" in body["html"]


def test_reports_build_preview_allows_payload(client: TestClient):
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "preview",
            "payload": _payload(),
            "candidate_id": "c-a",
            "include_html": False,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["report"]["provenance"]["export_mode"] == "preview"


def test_reports_build_final_rejects_client_payload(client: TestClient):
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": "x",
            "candidate_id": "c-a",
            "revision_id": "c-a",
            "payload": _payload(),
            "include_html": False,
        },
    )
    assert r.status_code == 422


def test_reports_build_final_requires_triple(client: TestClient):
    r = client.post(
        "/api/reports/build",
        json={"mode": "final", "include_html": False},
    )
    assert r.status_code == 422


def test_reports_build_rejects_dirty_candidate(client: TestClient):
    payload = _payload()
    payload["candidates"][0]["revision_status"] = "dirty"
    pid = _save_project(client, payload)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a",
            "include_html": False,
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "candidate_requires_revalidation"


def test_reports_build_preview_allow_stale_evaluation(client: TestClient):
    payload = _payload()
    payload["candidates"][0]["revision_status"] = "dirty"
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "preview",
            "payload": payload,
            "candidate_id": "c-a",
            "include_html": True,
            "allow_stale_evaluation": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report"]["status"] == "stale_evaluation"
    assert body["report"]["evaluation"]["evaluation_fresh"] is False
    assert "评价已过期" in body["html"]


def test_reports_build_final_revision_mismatch(client: TestClient):
    payload = _payload()
    payload["candidates"][0]["revision_id"] = "c-a:gen:deadbeef"
    pid = _save_project(client, payload)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "wrong-rev",
            "include_html": False,
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "revision_mismatch"


def test_reports_build_missing_candidate_id_is_404(client: TestClient):
    pid = _save_project(client)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-missing",
            "revision_id": "c-missing",
            "include_html": False,
        },
    )
    assert r.status_code == 404, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "candidate_not_found"
    assert detail["candidate_id"] == "c-missing"


def test_reports_build_missing_area_is_400(client: TestClient):
    payload = _payload()
    del payload["candidates"][0]["placements"][1]["area"]
    pid = _save_project(client, payload)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a",
            "include_html": False,
        },
    )
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "placement_area_missing"
    assert detail["room_id"] == "r2"


def test_reports_build_missing_requirement_spec_is_400(client: TestClient):
    payload = _payload()
    payload["requirement_spec"] = None
    pid = _save_project(client, payload)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a",
            "include_html": False,
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "requirement_spec_missing"


def test_reports_build_empty_placements_is_409(client: TestClient):
    payload = _payload()
    payload["candidates"][0]["placements"] = []
    pid = _save_project(client, payload)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a",
            "include_html": False,
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "invalid_candidate"


def test_reports_build_sanitizes_stored_malicious_svg(client: TestClient):
    payload = _payload()
    payload["candidates"][0]["svg"] = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<script>alert(1)</script><rect width="2" height="2"/></svg>'
    )
    pid = _save_project(client, payload)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a",
            "include_html": True,
        },
    )
    assert r.status_code == 200, r.text
    assert "<script" not in r.json()["html"].lower()


def test_source_revision_id_uses_revision_id_field():
    cand = _candidate()
    cand["revision_id"] = "c-a:gen:abc"
    report = build_design_report(
        project_name="Demo",
        requirement_spec=_payload()["requirement_spec"],
        program=_payload()["program"],
        candidate=cand,
        export_mode="final",
    )
    assert report.source_revision_id == "c-a:gen:abc"
    assert report.provenance.export_mode == "final"

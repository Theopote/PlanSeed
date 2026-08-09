"""Phase 7 — Report 层成体系测试（Integrity / Builder / HTML / Gate）。

命名对齐交付审查清单；Report renderer ≠ Evaluator：不重算分、不改写 Finding。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.main import create_app
from backend.services.report_builder import (
    ReportAreaMissingError,
    build_design_report,
)
from backend.services.report_html import render_report_html
from backend.services.report_svg_sanitize import sanitize_report_svg
from fastapi.testclient import TestClient
from packages.schema.report import GeometryOrigin
from packages.schema.scoring import DesignFinding, DesignScore, FindingSeverity
from pytest import raises


def _score() -> DesignScore:
    return DesignScore(
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
            ),
            DesignFinding(
                id="circ.warn",
                category="circulation",
                severity=FindingSeverity.WARNING,
                title="流线偏长",
                message="入户到主卧路径略长",
            ),
        ],
    )


def _candidate(**overrides) -> dict:
    base = {
        "id": "c-a",
        "seed": 42,
        "score": 76.5,
        "label": "A",
        "svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
            '<rect width="100" height="80" fill="#eee"/></svg>'
        ),
        "design_score": _score().model_dump(mode="json"),
        "provenance": {
            "solver_version": "test-s",
            "generator_version": "test-g",
            "evaluation_version": "test-e",
        },
        "revision_status": "generated",
        "revision_id": "c-a:gen:test",
        "placements": [
            {
                "room_id": "r1",
                "floor_id": "F1",
                "x": 0,
                "y": 0,
                "width": 4.0,
                "depth": 3.5,
                # 故意 ≠ width×depth，防止报告层重算
                "area": 99.0,
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
    base.update(overrides)
    return base


def _requirement_spec(**overrides) -> dict:
    base = {
        "floor_count": 2,
        "household": {"bedrooms": 3, "bathrooms": 2, "has_garage": True},
        "site": {"width": 11, "depth": 13},
        "preferences": {"prefer_south_facing_living": True},
        "relation_intents": [{"a": "厨房", "b": "餐厅", "kind": "near"}],
        "assumptions": [
            {
                "key": "site.setbacks",
                "value": 0,
                "reason": "未提供退界，按 0 处理",
                "source": "implicit",
            }
        ],
        "unknowns": [
            {"key": "site.entrance_edge", "description": "入口朝向未定"},
        ],
        "spaces": [],
    }
    base.update(overrides)
    return base


def _program() -> dict:
    return {
        "rooms": [
            {"id": "r1", "name": "客厅", "category": "living", "target_area": 20},
            {"id": "r2", "name": "厨房", "category": "wet", "target_area": 8},
        ]
    }


def _payload(candidate: dict | None = None) -> dict:
    return {
        "form": {},
        "program": _program(),
        "requirement_spec": _requirement_spec(),
        "candidates": [candidate or _candidate()],
        "selected_id": "c-a",
    }


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLANSEED_DB", str(tmp_path / "report-layer.db"))
    return TestClient(create_app())


def _save(client: TestClient, payload: dict | None = None) -> str:
    r = client.post(
        "/api/projects",
        json={"name": "Layer", "payload": payload or _payload()},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_report_from_generated_candidate():
    report = build_design_report(
        project_name="Gen",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(),
        export_mode="final",
    )
    assert report.status.value == "valid"
    assert report.project.geometry_origin == GeometryOrigin.SOLVER_GENERATED
    assert report.evaluation.evaluation_fresh is True
    assert report.provenance.export_mode == "final"


def test_report_from_validated_edit():
    cand = _candidate(
        revision_status="validated",
        mutations=[{"id": "m1", "kind": "move"}],
        revision_id="c-a:val:1",
    )
    report = build_design_report(
        project_name="Val",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=cand,
        export_mode="final",
    )
    assert report.project.geometry_origin == GeometryOrigin.USER_EDITED_VALIDATED
    assert report.project.edited is True
    assert report.status.value == "valid"
    assert report.source_revision_id == "c-a:val:1"


def test_dirty_candidate_rejected(client: TestClient):
    """dirty 禁止正式报告 — Phase 7 Integrity Gate P0。"""
    payload = _payload(_candidate(revision_status="dirty"))
    pid = _save(client, payload)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "c-a",
            "revision_id": "c-a:gen:test",
            "include_html": False,
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "candidate_requires_revalidation"


def test_missing_candidate_id_rejected(client: TestClient):
    pid = _save(client)
    r = client.post(
        "/api/reports/build",
        json={
            "mode": "final",
            "project_id": pid,
            "candidate_id": "does-not-exist",
            "revision_id": "x",
            "include_html": False,
        },
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "candidate_not_found"


def test_room_area_uses_canonical_area():
    """面积必须用 placements.area，禁止 width×depth。"""
    report = build_design_report(
        project_name="Area",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(),
    )
    living = next(r for r in report.room_schedule if r.room_id == "r1")
    assert living.width == 4.0
    assert living.depth == 3.5
    assert living.area == 99.0  # ≠ 14.0
    assert living.area != living.width * living.depth


def test_missing_area_rejected():
    cand = _candidate()
    del cand["placements"][0]["area"]
    with raises(ReportAreaMissingError) as ei:
        build_design_report(
            project_name="NoArea",
            requirement_spec=_requirement_spec(),
            program=_program(),
            candidate=cand,
        )
    assert ei.value.code == "placement_area_missing"
    assert ei.value.room_id == "r1"


def test_score_not_recomputed():
    """报告层不得另发明总分；Header / Evaluation 均取 DesignScore.total_score。"""
    report = build_design_report(
        project_name="Score",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(score=76.5),
    )
    assert report.candidate.total_score == 76.5
    assert report.evaluation.design_score is not None
    assert report.evaluation.design_score.total_score == 76.5
    assert report.evaluation.design_score.program_score == 80
    assert report.evaluation.design_score.spatial_score == 78


def test_header_score_ignores_stale_candidate_score_cache():
    """candidate.score 仅为 ranking cache；与 DesignScore 冲突时不得写入报告 Header。"""
    report = build_design_report(
        project_name="ScoreMismatch",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(score=81.0),
    )
    assert report.evaluation.design_score is not None
    assert report.evaluation.design_score.total_score == 76.5
    assert report.candidate.total_score == 76.5
    assert report.candidate.total_score != 81.0
    doc = render_report_html(report)
    assert '<span class="score">76</span>' in doc
    assert '<span class="score">81</span>' not in doc
    assert "81" not in doc


def test_findings_preserved():
    report = build_design_report(
        project_name="Find",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(),
    )
    assert len(report.findings) == 2
    assert report.findings[0].title == "比例尚可"
    assert report.findings[0].message == "主要房间比例在可接受范围"
    assert report.findings[0].severity == FindingSeverity.POSITIVE
    assert report.findings[1].id == "circ.warn"
    doc = render_report_html(report)
    assert "比例尚可" in doc
    assert "流线偏长" in doc


def test_assumptions_preserved():
    report = build_design_report(
        project_name="Assum",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(),
    )
    assert len(report.assumptions) == 1
    assert report.assumptions[0].key == "site.setbacks"
    assert report.assumptions[0].reason == "未提供退界，按 0 处理"
    doc = render_report_html(report)
    assert "site.setbacks" in doc
    assert "未提供退界" in doc


def test_unknowns_preserved():
    report = build_design_report(
        project_name="Unk",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(),
    )
    assert len(report.unknowns) == 1
    assert report.unknowns[0].key == "site.entrance_edge"
    assert report.unknowns[0].description == "入口朝向未定"
    doc = render_report_html(report)
    assert "site.entrance_edge" in doc
    assert "入口朝向未定" in doc


def test_provenance_preserved():
    report = build_design_report(
        project_name="Prov",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(),
        export_mode="final",
    )
    assert report.provenance.solver_version == "test-s"
    assert report.provenance.generator_version == "test-g"
    assert report.provenance.evaluation_version == "test-e"
    assert report.provenance.export_mode == "final"
    assert report.provenance.boundary_lines
    doc = render_report_html(report)
    assert "test-s" in doc
    assert "确定性求解器" in doc or "deterministic solver" in doc


def test_svg_sanitization():
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        "<script>alert(1)</script>"
        '<rect width="10" height="10" onclick="evil()"/>'
        '<image href="https://evil.example/x.png"/>'
        "</svg>"
    )
    out = sanitize_report_svg(dirty)
    assert "<script" not in out.lower()
    assert "onclick" not in out.lower()
    assert "<image" not in out.lower()
    assert "<rect" in out

    cand = _candidate(svg=dirty)
    report = build_design_report(
        project_name="Svg",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=cand,
    )
    doc = render_report_html(report)
    assert "<script" not in doc.lower()
    assert "onclick" not in doc.lower()


def test_html_escape():
    """普通文本须 escape；禁止把用户/解析内容当 HTML 插入。"""
    req = _requirement_spec(
        assumptions=[
            {
                "key": "x<script>",
                "value": True,
                "reason": "<img src=x onerror=alert(1)>",
            }
        ],
        unknowns=[
            {
                "key": "y",
                "description": "<b>未解决</b>",
            }
        ],
    )
    score = _score()
    score.findings = [
        DesignFinding(
            id="xss",
            category="spatial",
            severity=FindingSeverity.WARNING,
            title="<script>t</script>",
            message='msg "quoted" & <tag>',
        )
    ]
    cand = _candidate(design_score=score.model_dump(mode="json"))
    report = build_design_report(
        project_name="Proj <script>alert(1)</script>",
        requirement_spec=req,
        program=_program(),
        candidate=cand,
    )
    doc = render_report_html(report)
    assert "<script>t</script>" not in doc
    assert "&lt;script&gt;t&lt;/script&gt;" in doc
    assert "<img src=x" not in doc
    assert "&lt;img" in doc
    assert "<b>未解决</b>" not in doc
    assert "&lt;b&gt;未解决&lt;/b&gt;" in doc
    assert "Proj <script>" not in doc

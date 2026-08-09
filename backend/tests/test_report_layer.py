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


def test_invalid_validation_rejected():
    """validation.valid=false → INVALID；即便 revision_status=validated + design_score 残留。"""
    from backend.services.report_builder import (
        ReportBuildError,
        report_status_for_candidate,
    )
    from packages.schema.report import ReportStatus

    cand = _candidate(
        revision_status="validated",
        mutations=[{"id": "m1", "kind": "move"}],
        validation={"valid": False, "hard_violations": [], "soft_violations": [], "warnings": []},
    )
    assert report_status_for_candidate(cand) == ReportStatus.INVALID_CANDIDATE
    with raises(ReportBuildError) as ei:
        build_design_report(
            project_name="InvalidValidation",
            requirement_spec=_requirement_spec(),
            program=_program(),
            candidate=cand,
            export_mode="final",
        )
    assert ei.value.code == "invalid_candidate"


def test_invalid_validation_rejected_via_api(client: TestClient):
    """正式导出 API 拒绝 validation.valid=false。"""
    payload = _payload(
        _candidate(
            revision_status="validated",
            validation={"valid": False, "hard_violations": [], "soft_violations": [], "warnings": []},
        )
    )
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
    assert r.json()["detail"]["code"] == "invalid_candidate"


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
    """面积必须用 placements.area，禁止 width×depth；目标面积来自 program。"""
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
    assert living.target_area == 20.0
    assert living.area_delta == 79.0


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
    # 7.1：主文案用人话 reason，不把 key 当主视觉
    assert "未提供退界" in doc
    assert "06 假设与待决" in doc


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
    assert "入口朝向未定" in doc
    assert "06 假设与待决" in doc


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


def test_presentation_hierarchy_and_schedule_columns():
    """7.1：Cover→平面→面积表→评价；Assumptions 后置；主表无 room_id。"""
    report = build_design_report(
        project_name="Present",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=_candidate(),
    )
    doc = render_report_html(report)
    assert "01 设计要点" in doc
    assert "02 平面快照" in doc or "02 分层平面" in doc
    assert "03 空间面积表" in doc
    assert "04 设计评价" in doc
    assert "06 假设与待决" in doc
    assert "目标面积" in doc
    assert "宽 × 深" in doc
    # 主表不应再以 Id 列展示 room_id
    assert ">Id<" not in doc
    assert "r1" not in doc.split("07 溯源")[0]  # room_id 不进主视觉区
    # Assumptions 章节应在平面之后
    assert doc.index("02 ") < doc.index("06 假设与待决")
    assert "良好" in doc or "尚可" in doc or "可改善" in doc
    assert "主要优点" in doc
    assert "主要关注" in doc
    # 默认 fixture 无 north_angle → 不得画假 ↑N
    assert "北向未定义" in doc
    assert 'class="north"' not in doc


def test_blocking_unknown_on_cover():
    report = build_design_report(
        project_name="Block",
        requirement_spec=_requirement_spec(
            unknowns=[
                {
                    "key": "site.width",
                    "description": "场地宽度未定",
                    "priority": "blocking",
                }
            ]
        ),
        program=_program(),
        candidate=_candidate(),
    )
    doc = render_report_html(report)
    assert "阻塞性待决" in doc
    assert "场地宽度未定" in doc


def test_evaluation_presenter_deterministic():
    from backend.services.report_evaluation_presenter import present_evaluation

    score = _score()
    presented = present_evaluation(
        locale="zh-CN",
        design_score=score,
        findings=list(score.findings),
        key_intents=["两层住宅", "客厅朝南"],
        candidate_label="A",
    )
    assert len(presented.axes) == 7
    assert presented.axes[0].band_label == "良好"  # program 80
    assert any(a.score == 75 and a.band_label == "尚可" for a in presented.axes)
    assert presented.strengths[0].title == "比例尚可"
    assert presented.concerns[0].title == "流线偏长"
    assert "76" in presented.executive_summary
    assert "客厅朝南" in presented.executive_summary


def test_floor_plan_labels_localized():
    from packages.schema.report_i18n import present_floor_plan_label

    assert present_floor_plan_label("zh-CN", "F1") == "一楼平面"
    assert present_floor_plan_label("zh-CN", "F2") == "二楼平面"
    assert present_floor_plan_label("en-US", "F1") == "Level 1 plan"

    cand = _candidate(
        floor_svgs={
            "F1": '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
            "F2": '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
        }
    )
    report = build_design_report(
        project_name="Floors",
        requirement_spec=_requirement_spec(),
        program=_program(),
        candidate=cand,
    )
    assert [b.label for b in report.floor_plans] == ["一楼平面", "二楼平面"]
    doc = render_report_html(report)
    assert "一楼平面" in doc
    assert "目录" in doc
    assert "报告生成时间" in doc
    assert "功能配置" in doc or "空间品质" in doc


def test_north_angle_rotates_compass_and_unknown_omits_fake_n():
    """北针 = SiteCoordinateSystem 投影；未知禁止默认 ↑N。"""
    from backend.services.report_orientation import (
        north_arrow_css_rotation_deg,
        resolve_north_angle_deg,
    )
    from solver.geometry.site_coords import SiteCoordinateSystem

    assert north_arrow_css_rotation_deg(0) == 0.0
    assert north_arrow_css_rotation_deg(90) == -90.0
    # north_angle=90 → model west 朝世界北（与 CSS -90°=朝左一致）
    assert SiteCoordinateSystem(north_angle=90).model_edges_facing("north") == {"west"}

    assert resolve_north_angle_deg({"site": {"width": 11, "depth": 13}}) is None
    assert resolve_north_angle_deg({"site": {"north_angle": None}}) is None
    assert resolve_north_angle_deg({"site": {"north_angle": 90}}) == 90.0
    assert (
        resolve_north_angle_deg(
            {
                "site": {"width": 11},
                "assumptions": [
                    {"key": "site.north_angle", "value": 0, "reason": "default"}
                ],
            }
        )
        == 0.0
    )

    known = build_design_report(
        project_name="North",
        requirement_spec=_requirement_spec(site={"width": 11, "depth": 13, "north_angle": 90}),
        program=_program(),
        candidate=_candidate(),
    )
    assert known.floor_plans[0].north_angle_deg == 90.0
    doc = render_report_html(known)
    assert 'class="north"' in doc
    assert "rotate(-90" in doc
    assert "∠90°" in doc
    assert "北向未定义" not in doc

    unknown = build_design_report(
        project_name="NoNorth",
        requirement_spec=_requirement_spec(
            site={"width": 11, "depth": 13, "north_angle": None}
        ),
        program=_program(),
        candidate=_candidate(),
    )
    assert unknown.floor_plans[0].north_angle_deg is None
    doc_u = render_report_html(unknown)
    assert "北向未定义" in doc_u
    assert 'class="north"' not in doc_u

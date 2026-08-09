"""Phase 7.2.3 — DesignReport JSON 正式导出（≠ Project Snapshot）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from packages.schema.report import REPORT_SCHEMA_VERSION, DesignReport
from packages.schema.report_i18n import DEFAULT_REPORT_LOCALE, ReportLocale

from backend.routes.projects import APP_VERSION
from backend.services.export.svg_exporter import sanitize_export_filename
from backend.services.report_builder import ReportBuildError, build_design_report
from backend.services.report_svg_sanitize import sanitize_report_svg


@dataclass(frozen=True)
class JsonExportResult:
    body: bytes
    media_type: str
    filename: str
    report: DesignReport


def _sanitize_floor_svgs(report: DesignReport) -> DesignReport:
    plans = []
    for fp in report.floor_plans:
        if not (fp.svg or "").strip():
            plans.append(fp)
            continue
        plans.append(fp.model_copy(update={"svg": sanitize_report_svg(fp.svg)}))
    return report.model_copy(update={"floor_plans": plans})


def _strip_svgs(report: DesignReport) -> DesignReport:
    plans = [fp.model_copy(update={"svg": ""}) for fp in report.floor_plans]
    return report.model_copy(update={"floor_plans": plans})


def export_design_report_json(
    *,
    project_id: str,
    project_name: str,
    requirement_spec: dict[str, Any] | None,
    program: dict[str, Any] | None,
    candidate: dict[str, Any],
    candidate_label: str | None = None,
    locale: ReportLocale | str | None = None,
    include_svg: bool = True,
    app_version: str | None = None,
) -> JsonExportResult:
    """
    组装 DesignReport 并序列化为下载文件。

    禁止把 ProjectPayload / candidate.model_dump() 冒充报告。
    """
    report = build_design_report(
        project_name=project_name,
        project_id=project_id,
        app_version=app_version or APP_VERSION,
        requirement_spec=requirement_spec,
        program=program,
        candidate=candidate,
        export_mode="final",
        locale=locale or DEFAULT_REPORT_LOCALE,
    )
    if include_svg:
        report = _sanitize_floor_svgs(report)
    else:
        report = _strip_svgs(report)

    # 契约钉死：交付物必须是 DesignReport，不是工作台快照
    payload = report.model_dump(mode="json")
    if payload.get("report_schema_version") != REPORT_SCHEMA_VERSION:
        raise ReportBuildError(
            "report_schema_version_mismatch",
            "DesignReport.report_schema_version 与常量不一致",
            candidate_id=str(candidate.get("id") or "") or None,
        )
    for forbidden in ("candidates", "form", "locks", "selected_id", "program"):
        if forbidden in payload:
            raise ReportBuildError(
                "invalid_report_shape",
                f"DesignReport JSON 不得包含工作台字段 {forbidden}",
                candidate_id=str(candidate.get("id") or "") or None,
            )

    proj = sanitize_export_filename(project_name)
    label = sanitize_export_filename(
        candidate_label or str(candidate.get("label") or candidate.get("id") or "A")
    )
    filename = f"{proj}_{label}_DesignReport.json"
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return JsonExportResult(
        body=body,
        media_type="application/json; charset=utf-8",
        filename=filename,
        report=report,
    )


__all__ = [
    "JsonExportResult",
    "export_design_report_json",
]

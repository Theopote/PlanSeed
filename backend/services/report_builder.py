"""从项目快照 + 候选组装 DesignReport（不重评、不重算几何）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from packages.schema.report import (
    REPORT_BOUNDARY_LINES,
    CandidateSummary,
    DesignReport,
    EvaluationSummary,
    FloorPlanBlock,
    ProjectMetadata,
    ReportAssumption,
    ReportProvenance,
    ReportStatus,
    ReportUnknown,
    RequirementSummary,
    RoomScheduleRow,
)
from packages.schema.scoring import DesignScore


class ReportAreaMissingError(ValueError):
    """placement 缺权威 area — 报告层禁止用 width×depth 猜测。"""

    def __init__(self, *, room_id: str) -> None:
        self.room_id = room_id
        super().__init__(
            f"placement 缺少权威 area，无法组装报告面积表：room_id={room_id}"
        )


def report_status_for_candidate(candidate: dict[str, Any]) -> ReportStatus:
    """根据 revision_status 判定报告有效性（Integrity Gate）。"""
    revision = candidate.get("revision_status")
    if not candidate.get("id") and not candidate.get("placements"):
        return ReportStatus.INVALID_CANDIDATE
    if revision == "dirty":
        return ReportStatus.STALE_EVALUATION
    if revision in (None, "generated", "validated"):
        return ReportStatus.VALID
    return ReportStatus.INVALID_CANDIDATE


def build_design_report(
    *,
    project_name: str = "Untitled",
    project_id: str | None = None,
    app_version: str | None = None,
    requirement_spec: dict[str, Any] | None = None,
    program: dict[str, Any] | None = None,
    candidate: dict[str, Any],
) -> DesignReport:
    """
    权威组装：面积取 placements.area；评分/Finding 取 design_score。

    candidate 形状对齐 CandidatePayload（dict 或已 dump）。
    Dirty 候选仍可组装（status=stale_evaluation），但正式导出须由 API 拒绝。
    """
    req = requirement_spec or {}
    household = req.get("household") or {}
    site = req.get("site") or {}
    prefs = req.get("preferences") or {}

    floor_count = req.get("floor_count")
    bedrooms = household.get("bedrooms")
    bathrooms = household.get("bathrooms")
    has_garage = household.get("has_garage")
    south = prefs.get("prefer_south_facing_living")
    site_w = site.get("width")
    site_d = site.get("depth")

    key_intents = _key_intents(
        floor_count=floor_count,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        has_garage=has_garage,
        south=south,
        site_w=site_w,
        site_d=site_d,
        relations=req.get("relation_intents") or [],
        spaces=req.get("spaces") or [],
    )

    assumptions = [
        ReportAssumption(
            key=str(a.get("key", "")),
            value=a.get("value"),
            reason=str(a.get("reason") or ""),
            source=a.get("source"),
        )
        for a in (req.get("assumptions") or [])
        if isinstance(a, dict) and a.get("key")
    ]
    unknowns = [
        ReportUnknown(
            key=str(u.get("key", "")),
            description=str(u.get("description") or ""),
            priority=u.get("priority"),
        )
        for u in (req.get("unknowns") or [])
        if isinstance(u, dict) and u.get("key")
    ]

    design_score = _parse_design_score(candidate.get("design_score"))
    findings = list(design_score.findings) if design_score else []

    name_by_id = _room_names(program, req)
    schedule = _room_schedule(candidate.get("placements") or [], name_by_id)

    svg = str(candidate.get("svg") or "")
    floor_plans = [
        FloorPlanBlock(
            floor_id="all",
            label=str(candidate.get("label") or "Plan"),
            svg=svg,
        )
    ]

    revision = candidate.get("revision_status")
    edited = revision in ("dirty", "validated") or bool(candidate.get("mutations"))
    status = report_status_for_candidate(candidate)
    evaluation_fresh = status == ReportStatus.VALID
    cand_id = str(candidate.get("id") or "")
    parent = candidate.get("revision_parent_id")

    prov = candidate.get("provenance") or {}
    provenance = ReportProvenance(
        solver_version=prov.get("solver_version"),
        generator_version=prov.get("generator_version"),
        evaluation_version=prov.get("evaluation_version"),
        boundary_lines=list(REPORT_BOUNDARY_LINES),
    )

    total = candidate.get("score")
    if total is None and design_score is not None:
        total = design_score.total_score

    return DesignReport(
        status=status,
        source_revision_id=cand_id or None,
        project=ProjectMetadata(
            project_id=project_id,
            project_name=project_name or "Untitled",
            generated_at=datetime.now(timezone.utc).isoformat(),
            app_version=app_version,
            edited=edited,
        ),
        requirement=RequirementSummary(
            floor_count=floor_count if isinstance(floor_count, int) else None,
            bedrooms=bedrooms if isinstance(bedrooms, int) else None,
            bathrooms=bathrooms if isinstance(bathrooms, int) else None,
            has_garage=has_garage if isinstance(has_garage, bool) else None,
            prefer_south_facing_living=south if isinstance(south, bool) else None,
            site_width=float(site_w) if isinstance(site_w, (int, float)) else None,
            site_depth=float(site_d) if isinstance(site_d, (int, float)) else None,
            key_intents=key_intents,
        ),
        assumptions=assumptions,
        unknowns=unknowns,
        candidate=CandidateSummary(
            candidate_id=cand_id,
            label=str(candidate.get("label") or candidate.get("id") or "?"),
            seed=candidate.get("seed") if isinstance(candidate.get("seed"), int) else None,
            total_score=float(total) if isinstance(total, (int, float)) else None,
            revision_status=str(revision) if revision else None,
            revision_parent_id=str(parent) if parent else None,
        ),
        floor_plans=floor_plans,
        room_schedule=schedule,
        evaluation=EvaluationSummary(
            design_score=design_score,
            evaluation_fresh=evaluation_fresh,
        ),
        findings=findings,
        provenance=provenance,
    )


def _parse_design_score(raw: Any) -> DesignScore | None:
    if raw is None:
        return None
    if isinstance(raw, DesignScore):
        return raw
    if isinstance(raw, dict):
        try:
            return DesignScore.model_validate(raw)
        except Exception:
            return None
    return None


def _room_names(
    program: dict[str, Any] | None,
    req: dict[str, Any],
) -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(program, dict):
        for r in program.get("rooms") or []:
            if isinstance(r, dict) and r.get("id"):
                out[str(r["id"])] = str(r.get("name") or r["id"])
    for sp in req.get("spaces") or []:
        if isinstance(sp, dict) and sp.get("name"):
            # 无 id 时仅作展示补充
            name = str(sp["name"])
            out.setdefault(name, name)
    return out


def _room_schedule(
    placements: list[Any],
    name_by_id: dict[str, str],
) -> list[RoomScheduleRow]:
    rows: list[RoomScheduleRow] = []
    for p in placements:
        if not isinstance(p, dict):
            continue
        rid = str(p.get("room_id") or "")
        if not rid:
            continue
        w = float(p.get("width") or 0)
        d = float(p.get("depth") or 0)
        # 权威面积必须来自 placements；禁止 width×depth 猜测（非矩形/净毛面积会错）
        if p.get("area") is None:
            raise ReportAreaMissingError(room_id=rid)
        area = float(p["area"])
        rows.append(
            RoomScheduleRow(
                room_id=rid,
                name=name_by_id.get(rid, rid),
                floor_id=str(p.get("floor_id") or ""),
                width=w,
                depth=d,
                area=area,
            )
        )
    rows.sort(key=lambda r: (r.floor_id, r.name, r.room_id))
    return rows


def _key_intents(
    *,
    floor_count: Any,
    bedrooms: Any,
    bathrooms: Any,
    has_garage: Any,
    south: Any,
    site_w: Any,
    site_d: Any,
    relations: list[Any],
    spaces: list[Any],
) -> list[str]:
    lines: list[str] = []
    if isinstance(floor_count, int):
        lines.append(f"{floor_count}-story residence" if floor_count > 1 else "Single-story residence")
        if floor_count == 2:
            lines[-1] = "Two-story residence"
        elif floor_count == 3:
            lines[-1] = "Three-story residence"
    if isinstance(bedrooms, int):
        lines.append(f"{bedrooms} bedrooms")
    if isinstance(bathrooms, int):
        lines.append(f"{bathrooms} bathrooms")
    if has_garage is True:
        lines.append("With garage")
    elif has_garage is False:
        lines.append("No garage")
    if south is True:
        lines.append("Living room south-oriented")
    if isinstance(site_w, (int, float)) and isinstance(site_d, (int, float)):
        lines.append(f"Site {site_w:g} × {site_d:g} m")
    for r in relations:
        if not isinstance(r, dict):
            continue
        a, b, kind = r.get("a"), r.get("b"), r.get("kind")
        if a and b and kind:
            lines.append(f"{a} {kind} {b}")
    # 楼层偏好
    for sp in spaces:
        if not isinstance(sp, dict):
            continue
        name = sp.get("name")
        prefs = sp.get("floor_preference") or []
        if name and prefs:
            lines.append(f"{name} on {', '.join(str(p) for p in prefs)}")
        ori = sp.get("preferred_orientation")
        if name and ori and name not in ("客厅", "起居室"):
            lines.append(f"{name} faces {ori}")
    return lines

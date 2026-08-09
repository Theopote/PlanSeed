"""从项目快照 + 候选组装 DesignReport（不重评、不重算几何）。

原则：不能生成错误报告 — 权威数据缺失时 fail loudly，禁止 best-effort 猜测。
"""

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


class ReportBuildError(ValueError):
    """报告组装失败：缺权威数据或候选无效。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        room_id: str | None = None,
        candidate_id: str | None = None,
    ) -> None:
        self.code = code
        self.room_id = room_id
        self.candidate_id = candidate_id
        super().__init__(message)


class ReportAreaMissingError(ReportBuildError):
    """placement 缺权威 area — 报告层禁止用 width×depth 猜测。"""

    def __init__(self, *, room_id: str) -> None:
        super().__init__(
            "placement_area_missing",
            f"placement 缺少权威 area，无法组装报告面积表：room_id={room_id}",
            room_id=room_id,
        )


def report_status_for_candidate(candidate: dict[str, Any]) -> ReportStatus:
    """根据 revision / 结构完整性判定报告有效性（Integrity Gate）。"""
    if not isinstance(candidate, dict):
        return ReportStatus.INVALID_CANDIDATE
    if not candidate.get("id"):
        return ReportStatus.INVALID_CANDIDATE
    placements = candidate.get("placements")
    if not isinstance(placements, list) or len(placements) == 0:
        return ReportStatus.INVALID_CANDIDATE
    revision = candidate.get("revision_status")
    if revision == "dirty":
        return ReportStatus.STALE_EVALUATION
    if revision in (None, "generated", "validated"):
        # None：旧快照兼容，仍视为可导出；缺评分等由 builder 硬失败
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

    缺 requirement_spec / placements.area / design_score / svg 等 → ReportBuildError。
    Dirty 候选仍可组装（status=stale_evaluation），但正式导出须由 API 拒绝。
    """
    cand_id = str(candidate.get("id") or "") or None
    status = report_status_for_candidate(candidate)
    if status == ReportStatus.INVALID_CANDIDATE:
        raise ReportBuildError(
            "invalid_candidate",
            "候选无效（缺 id 或 placements），无法组装报告",
            candidate_id=cand_id,
        )

    req = _require_requirement_spec(requirement_spec)
    household = req.get("household") if isinstance(req.get("household"), dict) else {}
    site = req.get("site") if isinstance(req.get("site"), dict) else {}
    prefs = req.get("preferences") if isinstance(req.get("preferences"), dict) else {}

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

    design_score = _require_design_score(
        candidate.get("design_score"),
        candidate_id=cand_id,
    )
    findings = list(design_score.findings)

    name_by_id = _room_names(program, req)
    schedule = _room_schedule(candidate.get("placements") or [], name_by_id)

    svg = candidate.get("svg")
    if not isinstance(svg, str) or not svg.strip():
        raise ReportBuildError(
            "floor_plan_svg_missing",
            "候选缺少平面图 SVG，无法组装正式报告",
            candidate_id=cand_id,
        )
    floor_plans = [
        FloorPlanBlock(
            floor_id="all",
            label=str(candidate.get("label") or "Plan"),
            svg=svg,
        )
    ]

    revision = candidate.get("revision_status")
    edited = revision in ("dirty", "validated") or bool(candidate.get("mutations"))
    evaluation_fresh = status == ReportStatus.VALID
    parent = candidate.get("revision_parent_id")

    prov = candidate.get("provenance") or {}
    provenance = ReportProvenance(
        solver_version=prov.get("solver_version") if isinstance(prov, dict) else None,
        generator_version=prov.get("generator_version") if isinstance(prov, dict) else None,
        evaluation_version=prov.get("evaluation_version") if isinstance(prov, dict) else None,
        boundary_lines=list(REPORT_BOUNDARY_LINES),
    )

    total = candidate.get("score")
    if total is None:
        total = design_score.total_score

    return DesignReport(
        status=status,
        source_revision_id=cand_id,
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
            candidate_id=cand_id or "",
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


def _require_requirement_spec(requirement_spec: dict[str, Any] | None) -> dict[str, Any]:
    if requirement_spec is None:
        raise ReportBuildError(
            "requirement_spec_missing",
            "缺少 RequirementSpec，无法组装正式报告的 Key Intent / Assumptions / Unknowns",
        )
    if not isinstance(requirement_spec, dict):
        raise ReportBuildError(
            "requirement_spec_invalid",
            "RequirementSpec 格式无效，无法组装正式报告",
        )
    if not requirement_spec:
        raise ReportBuildError(
            "requirement_spec_missing",
            "RequirementSpec 为空，无法组装正式报告",
        )
    return requirement_spec


def _require_design_score(raw: Any, *, candidate_id: str | None) -> DesignScore:
    if raw is None:
        raise ReportBuildError(
            "design_score_missing",
            "候选缺少 DesignScore，无法组装正式评价报告",
            candidate_id=candidate_id,
        )
    if isinstance(raw, DesignScore):
        return raw
    if isinstance(raw, dict):
        try:
            return DesignScore.model_validate(raw)
        except Exception as exc:
            raise ReportBuildError(
                "design_score_invalid",
                f"候选 DesignScore 无法解析：{exc}",
                candidate_id=candidate_id,
            ) from exc
    raise ReportBuildError(
        "design_score_invalid",
        "候选 DesignScore 类型无效",
        candidate_id=candidate_id,
    )


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
            name = str(sp["name"])
            out.setdefault(name, name)
    return out


def _room_schedule(
    placements: list[Any],
    name_by_id: dict[str, str],
) -> list[RoomScheduleRow]:
    if not placements:
        raise ReportBuildError(
            "placements_missing",
            "候选无 placements，无法组装报告面积表",
        )
    rows: list[RoomScheduleRow] = []
    for i, p in enumerate(placements):
        if not isinstance(p, dict):
            raise ReportBuildError(
                "placement_invalid",
                f"placement[{i}] 格式无效，无法组装报告",
            )
        rid = p.get("room_id")
        if not rid:
            raise ReportBuildError(
                "placement_room_id_missing",
                f"placement[{i}] 缺少 room_id，无法组装报告",
            )
        rid_s = str(rid)
        if p.get("width") is None or p.get("depth") is None:
            raise ReportBuildError(
                "placement_dimensions_missing",
                f"placement 缺少 width/depth：room_id={rid_s}",
                room_id=rid_s,
            )
        w = float(p["width"])
        d = float(p["depth"])
        if p.get("area") is None:
            raise ReportAreaMissingError(room_id=rid_s)
        area = float(p["area"])
        rows.append(
            RoomScheduleRow(
                room_id=rid_s,
                name=name_by_id.get(rid_s, rid_s),
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

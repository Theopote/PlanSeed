"""从项目快照 + 候选组装 DesignReport（不重评、不重算几何）。

原则：不能生成错误报告 — 权威数据缺失时 fail loudly，禁止 best-effort 猜测。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from packages.schema.report import (
    CandidateSummary,
    DesignReport,
    EvaluationSummary,
    FloorPlanBlock,
    GeometryOrigin,
    ProjectMetadata,
    ReportAssumption,
    ReportProvenance,
    ReportStatus,
    ReportUnknown,
    RequirementSummary,
    RoomScheduleRow,
)
from packages.schema.report_i18n import (
    ReportLocale,
    boundary_lines_for_locale,
    format_key_intents,
    normalize_report_locale,
    present_floor_plan_label,
    tr,
)
from packages.schema.scoring import DesignScore

from backend.services.serialization import resolve_revision_id


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
    """根据 revision / 结构完整性 / validation 判定报告有效性（Integrity Gate）。"""
    if not isinstance(candidate, dict):
        return ReportStatus.INVALID_CANDIDATE
    if not candidate.get("id"):
        return ReportStatus.INVALID_CANDIDATE
    placements = candidate.get("placements")
    if not isinstance(placements, list) or len(placements) == 0:
        return ReportStatus.INVALID_CANDIDATE
    # validation 存在且 valid=False → 无效（不依赖「正常 pipeline 不会出现」）
    validation = candidate.get("validation")
    if isinstance(validation, dict) and validation.get("valid") is False:
        return ReportStatus.INVALID_CANDIDATE
    revision = candidate.get("revision_status")
    if revision == "dirty":
        return ReportStatus.STALE_EVALUATION
    if revision in (None, "generated", "validated"):
        # None：旧快照兼容，仍视为可导出；缺评分等由 builder 硬失败
        return ReportStatus.VALID
    return ReportStatus.INVALID_CANDIDATE


def geometry_origin_for_candidate(candidate: dict[str, Any]) -> GeometryOrigin:
    """Solver Generated / User Edited + Validated / User Edited + Stale。"""
    revision = candidate.get("revision_status")
    if revision == "dirty":
        return GeometryOrigin.USER_EDITED_STALE
    if revision == "validated":
        return GeometryOrigin.USER_EDITED_VALIDATED
    # generated / None：有 mutation 日志仍视为已编辑并验证过（可交付）
    if candidate.get("mutations"):
        return GeometryOrigin.USER_EDITED_VALIDATED
    return GeometryOrigin.SOLVER_GENERATED


def build_design_report(
    *,
    project_name: str = "Untitled",
    project_id: str | None = None,
    app_version: str | None = None,
    requirement_spec: dict[str, Any] | None = None,
    program: dict[str, Any] | None = None,
    candidate: dict[str, Any],
    export_mode: str = "preview",
    locale: ReportLocale | str | None = None,
) -> DesignReport:
    """
    权威组装：面积取 placements.area；评分/Finding 取 design_score。

    缺 requirement_spec / placements.area / design_score / svg 等 → ReportBuildError。
    Dirty 候选仍可组装（status=stale_evaluation），但正式导出须由 API 拒绝。
    export_mode: preview（可 client payload）| final（须 store + revision_id）。
    locale: Alpha 默认 zh-CN；文案集中在 report_i18n。
    """
    report_locale = normalize_report_locale(locale)
    cand_id = str(candidate.get("id") or "") or None
    status = report_status_for_candidate(candidate)
    if status == ReportStatus.INVALID_CANDIDATE:
        raise ReportBuildError(
            "invalid_candidate",
            "候选无效（缺 id / placements，或 validation.valid=false），无法组装报告",
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

    key_intents = format_key_intents(
        report_locale,
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
    target_by_id = _room_target_areas(program)
    schedule = _room_schedule(
        candidate.get("placements") or [],
        name_by_id,
        target_by_id,
    )

    svg = candidate.get("svg")
    if not isinstance(svg, str) or not svg.strip():
        raise ReportBuildError(
            "floor_plan_svg_missing",
            "候选缺少平面图 SVG，无法组装正式报告",
            candidate_id=cand_id,
        )
    # 优先消费 candidate.floor_svgs（serializer / render_floor_svg）；
    # 否则 Alpha 退回整图 svg（floor_id=all）。禁止在此切 SVG DOM。
    floor_plans = _floor_plan_blocks(
        candidate, svg=svg, locale=report_locale
    )

    revision = candidate.get("revision_status")
    origin = geometry_origin_for_candidate(candidate)
    edited = origin != GeometryOrigin.SOLVER_GENERATED
    evaluation_fresh = status == ReportStatus.VALID
    parent = candidate.get("revision_parent_id")

    prov = candidate.get("provenance") or {}
    mode = export_mode if export_mode in ("preview", "final") else "preview"
    provenance = ReportProvenance(
        solver_version=prov.get("solver_version") if isinstance(prov, dict) else None,
        generator_version=prov.get("generator_version") if isinstance(prov, dict) else None,
        evaluation_version=prov.get("evaluation_version") if isinstance(prov, dict) else None,
        export_mode=mode,
        boundary_lines=boundary_lines_for_locale(report_locale),
    )

    # 报告总分只取 DesignScore（评价事实源）；candidate.score 仅为 ranking cache，不得覆盖。
    total = design_score.total_score

    rev_id = resolve_revision_id(candidate) or cand_id

    return DesignReport(
        status=status,
        source_revision_id=rev_id,
        project=ProjectMetadata(
            project_id=project_id,
            project_name=project_name or "Untitled",
            generated_at=datetime.now(UTC).isoformat(),
            app_version=app_version,
            locale=report_locale,
            geometry_origin=origin,
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
            total_score=float(total),
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


def _room_target_areas(program: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(program, dict):
        return out
    for r in program.get("rooms") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        raw = r.get("target_area")
        if isinstance(raw, (int, float)):
            out[str(r["id"])] = float(raw)
    return out


def _room_schedule(
    placements: list[Any],
    name_by_id: dict[str, str],
    target_by_id: dict[str, float] | None = None,
) -> list[RoomScheduleRow]:
    targets = target_by_id or {}
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
        target = targets.get(rid_s)
        delta = round(area - target, 2) if target is not None else None
        rows.append(
            RoomScheduleRow(
                room_id=rid_s,
                name=name_by_id.get(rid_s, rid_s),
                floor_id=str(p.get("floor_id") or ""),
                width=w,
                depth=d,
                area=area,
                target_area=target,
                area_delta=delta,
            )
        )
    rows.sort(key=lambda r: (r.floor_id, r.name, r.room_id))
    return rows


def _floor_plan_blocks(
    candidate: dict[str, Any],
    *,
    svg: str,
    locale: ReportLocale,
) -> list[FloorPlanBlock]:
    """
    消费候选已序列化的平面 SVG。

    - 若有 `floor_svgs: {floor_id: svg}`（serializer）→ 按楼层展开
    - 否则：单块 Candidate SVG snapshot（floor_id=all）
    禁止在此解析/裁剪 SVG DOM。
    """
    raw = candidate.get("floor_svgs")
    if isinstance(raw, dict) and raw:
        blocks: list[FloorPlanBlock] = []
        for fid, floor_svg in raw.items():
            if not isinstance(floor_svg, str) or not floor_svg.strip():
                continue
            fid_s = str(fid)
            blocks.append(
                FloorPlanBlock(
                    floor_id=fid_s,
                    label=present_floor_plan_label(locale, fid_s),
                    svg=floor_svg,
                )
            )
        if blocks:
            blocks.sort(key=lambda b: b.floor_id)
            return blocks
    return [
        FloorPlanBlock(
            floor_id="all",
            label=tr(locale, "label.candidate_snapshot"),
            svg=svg,
        )
    ]

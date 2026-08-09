"""DesignReport 文案目录 — 禁止散落硬编码字符串。

Alpha 默认 ReportLocale.ZH_CN；en-US 预留完整条目供后续切换。
不依赖 report.py（避免循环导入）。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ReportLocale(StrEnum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"


DEFAULT_REPORT_LOCALE = ReportLocale.ZH_CN

# GeometryOrigin.value → 文案 key
_ORIGIN_KEYS: dict[str, str] = {
    "solver_generated": "geometry.solver_generated",
    "user_edited_validated": "geometry.user_edited_validated",
    "user_edited_stale": "geometry.user_edited_stale",
}

# relation kind → 展示（未收录则原样）
_RELATION_KIND: dict[ReportLocale, dict[str, str]] = {
    ReportLocale.ZH_CN: {
        "near": "邻近",
        "separation": "分离",
        "open_connection": "开敞连接",
        "access": "可到达",
        "visual_connection": "视线连通",
        "adjacency": "相邻",
    },
    ReportLocale.EN_US: {
        "near": "near",
        "separation": "separation",
        "open_connection": "open connection",
        "access": "access",
        "visual_connection": "visual connection",
        "adjacency": "adjacency",
    },
}

_STRINGS: dict[ReportLocale, dict[str, str]] = {
    ReportLocale.ZH_CN: {
        "geometry.solver_generated": "求解器生成",
        "geometry.user_edited_validated": "用户编辑 · 已验证",
        "geometry.user_edited_stale": "用户编辑 · 评价过期",
        "stale.title": "评价已过期",
        "stale.body": "几何已修改；下列评分 / Findings 可能不对应当前平面，不得作为正式评价交付。",
        "empty.intents": "（无显式要点）",
        "empty.list": "（无）",
        "empty.placements": "（无房间）",
        "empty.scores": "（无评分）",
        "empty.plans": "（无平面图）",
        "cover.eyebrow": "PlanSeed 设计报告",
        "cover.summary": "摘要",
        "section.brief": "01 设计要点",
        "section.key_intent": "设计要点",
        "section.assumptions": "假设",
        "section.unresolved": "待决问题",
        "section.assumptions_unknowns": "06 假设与待决",
        "section.floor_plans": "02 分层平面",
        "section.plan_snapshot": "02 平面快照",
        "section.room_schedule": "03 空间面积表",
        "section.evaluation": "04 设计评价",
        "section.findings": "05 关键发现",
        "section.provenance": "07 溯源",
        "section.strengths": "主要优点",
        "section.concerns": "主要关注",
        "section.blocking": "阻塞性待决",
        "table.room": "房间",
        "table.floor": "楼层",
        "table.id": "Id",
        "table.w": "宽",
        "table.d": "深",
        "table.wxd": "宽 × 深",
        "table.area": "实际面积 m²",
        "table.target_area": "目标面积 m²",
        "table.delta": "差值 m²",
        "table.axis": "维度",
        "table.score": "分数",
        "table.band": "评价",
        "meta.candidate": "方案",
        "meta.id": "候选 id",
        "meta.evaluation_fresh": "评价新鲜",
        "meta.source_revision": "revision",
        "meta.export": "导出",
        "meta.north": "北",
        "meta.scale": "单位：米 · 图示为方案示意（打印时请以标注尺寸为准）",
        "meta.legend": "图例：房间填充 · 墙体边界 · 标注为房间名与面积",
        "meta.report_generated_at": "报告生成时间",
        "meta.toc": "目录",
        "band.good": "良好",
        "band.fair": "尚可",
        "band.improve": "可改善",
        "summary.basic": "方案 {label} 综合评分 {score}（{band}）。要点：{intents}。",
        "summary.minimal": "方案 {label} 综合评分 {score}（{band}）。",
        "summary.with_strength": "方案 {label} 综合评分 {score}（{band}）。要点：{intents}。亮点：{strength}。",
        "summary.with_concern": "方案 {label} 综合评分 {score}（{band}）。要点：{intents}。需关注：{concern}。",
        "summary.with_concern_no_intent": "方案 {label} 综合评分 {score}（{band}）。需关注：{concern}。",
        "intent.single_story": "单层住宅",
        "intent.two_story": "两层住宅",
        "intent.three_story": "三层住宅",
        "intent.n_story": "{n} 层住宅",
        "intent.bedrooms": "{n} 间卧室",
        "intent.bathrooms": "{n} 间卫生间",
        "intent.with_garage": "带车库",
        "intent.no_garage": "无车库",
        "intent.south_living": "客厅朝南",
        "intent.site": "场地 {w:g} × {d:g} m",
        "intent.relation.near": "{a}靠近{b}",
        "intent.relation.separation": "{a}与{b}保持距离",
        "intent.relation.open_connection": "{a}与{b}开敞连通",
        "intent.relation.access": "{a}可直接进入{b}",
        "intent.relation.visual_connection": "{a}与{b}视线连通",
        "intent.relation.adjacency": "{a}与{b}相邻",
        "intent.relation.fallback": "{a}与{b}（{kind}）",
        "intent.space_floor": "{name} 位于 {floors}",
        "intent.space_orient": "{name} 朝向 {ori}",
        "axis.program": "功能配置",
        "axis.spatial": "空间品质",
        "axis.circulation": "流线组织",
        "axis.privacy": "私密分区",
        "axis.environment": "环境与朝向",
        "axis.technical": "技术可行性",
        "axis.robustness": "方案稳健性",
        "boundary.req": "需求解释：本地 LLM + 确定性语义流水线",
        "boundary.geom": "几何：PlanSeed 确定性求解器",
        "boundary.eval": "评价：PlanSeed 住宅启发式评价器",
        "boundary.summary": "AI 解释设计意图；确定性求解器生成并评价几何。",
        "label.candidate_snapshot": "方案平面快照",
        "label.plan": "平面",
        "label.floor_plan": "{name}平面",
        "label.floor_1": "一楼",
        "label.floor_2": "二楼",
        "label.floor_3": "三楼",
        "label.floor_n": "{n}楼",
    },
    ReportLocale.EN_US: {
        "geometry.solver_generated": "Solver Generated",
        "geometry.user_edited_validated": "User Edited + Validated",
        "geometry.user_edited_stale": "User Edited + Stale",
        "stale.title": "STALE EVALUATION",
        "stale.body": (
            "Geometry was modified; scores / findings below may not match "
            "the current plan. Not valid as a formal evaluation deliverable."
        ),
        "empty.intents": "(no explicit intents)",
        "empty.list": "(none)",
        "empty.placements": "(no rooms)",
        "empty.scores": "(no scores)",
        "empty.plans": "(no floor plans)",
        "cover.eyebrow": "PlanSeed Design Report",
        "cover.summary": "Executive Summary",
        "section.brief": "01 Design Brief",
        "section.key_intent": "Key Intent",
        "section.assumptions": "Assumptions",
        "section.unresolved": "Open Questions",
        "section.assumptions_unknowns": "06 Assumptions & Open Questions",
        "section.floor_plans": "02 Floor Plans",
        "section.plan_snapshot": "02 Plan Snapshot",
        "section.room_schedule": "03 Space Schedule",
        "section.evaluation": "04 Design Evaluation",
        "section.findings": "05 Key Findings",
        "section.provenance": "07 Provenance",
        "section.strengths": "Top strengths",
        "section.concerns": "Top concerns",
        "section.blocking": "Blocking unknowns",
        "table.room": "Room",
        "table.floor": "Floor",
        "table.id": "Id",
        "table.w": "W",
        "table.d": "D",
        "table.wxd": "W × D",
        "table.area": "Actual m²",
        "table.target_area": "Target m²",
        "table.delta": "Delta m²",
        "table.axis": "Axis",
        "table.score": "Score",
        "table.band": "Band",
        "meta.candidate": "Candidate",
        "meta.id": "candidate id",
        "meta.evaluation_fresh": "evaluation_fresh",
        "meta.source_revision": "source_revision",
        "meta.export": "export",
        "meta.north": "N",
        "meta.scale": "Units: metres · Diagrammatic (use dimension labels when printing)",
        "meta.legend": "Legend: room fill · wall boundary · labels show name and area",
        "meta.report_generated_at": "Report generated at",
        "meta.toc": "Contents",
        "band.good": "Good",
        "band.fair": "Fair",
        "band.improve": "Needs work",
        "summary.basic": "Candidate {label} scores {score} ({band}). Brief: {intents}.",
        "summary.minimal": "Candidate {label} scores {score} ({band}).",
        "summary.with_strength": (
            "Candidate {label} scores {score} ({band}). Brief: {intents}. "
            "Strength: {strength}."
        ),
        "summary.with_concern": (
            "Candidate {label} scores {score} ({band}). Brief: {intents}. "
            "Watch: {concern}."
        ),
        "summary.with_concern_no_intent": (
            "Candidate {label} scores {score} ({band}). Watch: {concern}."
        ),
        "intent.single_story": "Single-story residence",
        "intent.two_story": "Two-story residence",
        "intent.three_story": "Three-story residence",
        "intent.n_story": "{n}-story residence",
        "intent.bedrooms": "{n} bedrooms",
        "intent.bathrooms": "{n} bathrooms",
        "intent.with_garage": "With garage",
        "intent.no_garage": "No garage",
        "intent.south_living": "Living room south-oriented",
        "intent.site": "Site {w:g} × {d:g} m",
        "intent.relation.near": "{a} is near {b}",
        "intent.relation.separation": "{a} is kept apart from {b}",
        "intent.relation.open_connection": "{a} and {b} are openly connected",
        "intent.relation.access": "{a} can access {b} directly",
        "intent.relation.visual_connection": "{a} and {b} share a visual connection",
        "intent.relation.adjacency": "{a} is adjacent to {b}",
        "intent.relation.fallback": "{a} ↔ {b} ({kind})",
        "intent.space_floor": "{name} on {floors}",
        "intent.space_orient": "{name} faces {ori}",
        "axis.program": "Program",
        "axis.spatial": "Spatial quality",
        "axis.circulation": "Circulation",
        "axis.privacy": "Privacy",
        "axis.environment": "Environment & orientation",
        "axis.technical": "Technical feasibility",
        "axis.robustness": "Robustness",
        "boundary.req": "Requirement interpretation: Local LLM + deterministic semantic pipeline",
        "boundary.geom": "Geometry: PlanSeed deterministic solver",
        "boundary.eval": "Evaluation: PlanSeed residential heuristic evaluator",
        "boundary.summary": (
            "AI interpreted design intent; deterministic solver generated "
            "and evaluated geometry."
        ),
        "label.candidate_snapshot": "Candidate plan snapshot",
        "label.plan": "Plan",
        "label.floor_plan": "{name} plan",
        "label.floor_1": "Level 1",
        "label.floor_2": "Level 2",
        "label.floor_3": "Level 3",
        "label.floor_n": "Level {n}",
    },
}


def normalize_report_locale(raw: str | ReportLocale | None) -> ReportLocale:
    if raw is None:
        return DEFAULT_REPORT_LOCALE
    if isinstance(raw, ReportLocale):
        return raw
    text = str(raw).strip()
    for loc in ReportLocale:
        if text == loc.value or text.lower() == loc.value.lower():
            return loc
    # 兼容简写
    if text.lower() in ("zh", "zh_cn", "zh-cn", "cn"):
        return ReportLocale.ZH_CN
    if text.lower() in ("en", "en_us", "en-us", "us"):
        return ReportLocale.EN_US
    return DEFAULT_REPORT_LOCALE


def tr(locale: ReportLocale, key: str, **kwargs: Any) -> str:
    """取文案；缺 key 时回退 en-US 再回退 key 本身。"""
    loc = normalize_report_locale(locale)
    catalog = _STRINGS.get(loc) or _STRINGS[DEFAULT_REPORT_LOCALE]
    template = catalog.get(key)
    if template is None:
        template = _STRINGS[ReportLocale.EN_US].get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template


def geometry_origin_label(locale: ReportLocale, origin: Any) -> str:
    value = getattr(origin, "value", origin)
    key = _ORIGIN_KEYS.get(str(value), "geometry.solver_generated")
    return tr(locale, key)


def relation_kind_label(locale: ReportLocale, kind: str) -> str:
    table = _RELATION_KIND.get(normalize_report_locale(locale), {})
    return table.get(kind, kind)


def present_relation_intent(
    locale: ReportLocale,
    a: str,
    b: str,
    kind: str,
) -> str:
    """
    RelationPresenter：把 relation enum 收成用户可读短句。

    禁止输出「厨房 near 餐厅」这类 enum 名。
    """
    loc = normalize_report_locale(locale)
    kind_s = str(kind).strip()
    key = f"intent.relation.{kind_s}"
    catalog = _STRINGS.get(loc) or _STRINGS[DEFAULT_REPORT_LOCALE]
    if key in catalog:
        return tr(loc, key, a=a, b=b)
    return tr(
        loc,
        "intent.relation.fallback",
        a=a,
        b=b,
        kind=relation_kind_label(loc, kind_s),
    )


def present_floor_plan_label(locale: ReportLocale | str, floor_id: str) -> str:
    """楼层平面标题：F1 → 一楼平面 / Level 1 plan；禁止只甩裸 id。"""
    loc = normalize_report_locale(locale)
    fid = str(floor_id).strip()
    if not fid or fid == "all":
        return tr(loc, "label.candidate_snapshot")
    digits = "".join(ch for ch in fid if ch.isdigit())
    if digits == "1":
        name = tr(loc, "label.floor_1")
    elif digits == "2":
        name = tr(loc, "label.floor_2")
    elif digits == "3":
        name = tr(loc, "label.floor_3")
    elif digits:
        name = tr(loc, "label.floor_n", n=digits)
    else:
        name = fid
    return tr(loc, "label.floor_plan", name=name)


def boundary_lines_for_locale(locale: ReportLocale) -> list[str]:
    return [
        tr(locale, "boundary.req"),
        tr(locale, "boundary.geom"),
        tr(locale, "boundary.eval"),
        tr(locale, "boundary.summary"),
    ]


def format_key_intents(
    locale: ReportLocale,
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
    loc = normalize_report_locale(locale)
    lines: list[str] = []
    if isinstance(floor_count, int):
        if floor_count == 1:
            lines.append(tr(loc, "intent.single_story"))
        elif floor_count == 2:
            lines.append(tr(loc, "intent.two_story"))
        elif floor_count == 3:
            lines.append(tr(loc, "intent.three_story"))
        else:
            lines.append(tr(loc, "intent.n_story", n=floor_count))
    if isinstance(bedrooms, int):
        lines.append(tr(loc, "intent.bedrooms", n=bedrooms))
    if isinstance(bathrooms, int):
        lines.append(tr(loc, "intent.bathrooms", n=bathrooms))
    if has_garage is True:
        lines.append(tr(loc, "intent.with_garage"))
    elif has_garage is False:
        lines.append(tr(loc, "intent.no_garage"))
    if south is True:
        lines.append(tr(loc, "intent.south_living"))
    if isinstance(site_w, (int, float)) and isinstance(site_d, (int, float)):
        lines.append(tr(loc, "intent.site", w=site_w, d=site_d))
    for r in relations:
        if not isinstance(r, dict):
            continue
        a, b, kind = r.get("a"), r.get("b"), r.get("kind")
        if a and b and kind:
            lines.append(present_relation_intent(loc, str(a), str(b), str(kind)))
    for sp in spaces:
        if not isinstance(sp, dict):
            continue
        name = sp.get("name")
        prefs = sp.get("floor_preference") or []
        if name and prefs:
            lines.append(
                tr(
                    loc,
                    "intent.space_floor",
                    name=name,
                    floors=", ".join(str(p) for p in prefs),
                )
            )
        ori = sp.get("preferred_orientation")
        if name and ori and name not in ("客厅", "起居室", "living", "Living"):
            lines.append(tr(loc, "intent.space_orient", name=name, ori=ori))
    return lines

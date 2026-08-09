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
        "empty.placements": "（无 placements）",
        "empty.scores": "（无评分）",
        "empty.plans": "（无平面图）",
        "section.key_intent": "设计要点",
        "section.assumptions": "假设",
        "section.unresolved": "未解决",
        "section.floor_plans": "分层平面",
        "section.plan_snapshot": "平面快照",
        "section.room_schedule": "房间面积表",
        "section.evaluation": "评价",
        "section.findings": "发现",
        "section.provenance": "溯源",
        "table.room": "房间",
        "table.floor": "楼层",
        "table.id": "Id",
        "table.w": "宽",
        "table.d": "深",
        "table.area": "面积 m²",
        "table.axis": "维度",
        "table.score": "分数",
        "meta.candidate": "方案",
        "meta.id": "id",
        "meta.evaluation_fresh": "评价新鲜",
        "meta.source_revision": "revision",
        "meta.export": "导出",
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
        "intent.relation": "{a} {kind} {b}",
        "intent.space_floor": "{name} 位于 {floors}",
        "intent.space_orient": "{name} 朝向 {ori}",
        "axis.program": "程序",
        "axis.spatial": "空间",
        "axis.circulation": "流线",
        "axis.privacy": "私密",
        "axis.environment": "环境",
        "axis.technical": "技术",
        "axis.robustness": "稳健",
        "boundary.req": "需求解释：本地 LLM + 确定性语义流水线",
        "boundary.geom": "几何：PlanSeed 确定性求解器",
        "boundary.eval": "评价：PlanSeed 住宅启发式评价器",
        "boundary.summary": "AI 解释设计意图；确定性求解器生成并评价几何。",
        "label.candidate_snapshot": "方案平面快照",
        "label.plan": "平面",
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
        "empty.placements": "(no placements)",
        "empty.scores": "(no scores)",
        "empty.plans": "(no floor plans)",
        "section.key_intent": "Key Intent",
        "section.assumptions": "Assumptions",
        "section.unresolved": "Unresolved",
        "section.floor_plans": "Floor Plans",
        "section.plan_snapshot": "Plan Snapshot",
        "section.room_schedule": "Room Schedule",
        "section.evaluation": "Evaluation",
        "section.findings": "Findings",
        "section.provenance": "Provenance",
        "table.room": "Room",
        "table.floor": "Floor",
        "table.id": "Id",
        "table.w": "W",
        "table.d": "D",
        "table.area": "Area m²",
        "table.axis": "Axis",
        "table.score": "Score",
        "meta.candidate": "Candidate",
        "meta.id": "id",
        "meta.evaluation_fresh": "evaluation_fresh",
        "meta.source_revision": "source_revision",
        "meta.export": "export",
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
        "intent.relation": "{a} {kind} {b}",
        "intent.space_floor": "{name} on {floors}",
        "intent.space_orient": "{name} faces {ori}",
        "axis.program": "Program",
        "axis.spatial": "Spatial",
        "axis.circulation": "Circulation",
        "axis.privacy": "Privacy",
        "axis.environment": "Environment",
        "axis.technical": "Technical",
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
            lines.append(
                tr(
                    loc,
                    "intent.relation",
                    a=a,
                    b=b,
                    kind=relation_kind_label(loc, str(kind)),
                )
            )
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

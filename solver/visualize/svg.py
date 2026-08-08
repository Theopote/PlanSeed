"""
将 LayoutCandidate 渲染为 SVG（米坐标 = SVG 用户单位）。

y=0 为 model north（图上方），与 solver 几何一致。
Debug 叠加：north_angle、入口、临路、StairCore、WetStack。
"""

from __future__ import annotations

import html
from pathlib import Path

from packages.schema.layout import FloorLayout, LayoutCandidate, RoomPlacement
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import AccessGraph, SpaceConnectionType

_CATEGORY_FILL: dict[str, str] = {
    "public": "#E8D5B5",
    "private": "#C5D4E8",
    "wet": "#9EC5C0",
    "service": "#D4C4A8",
    "circulation": "#E0E0E0",
    "other": "#DDD8D0",
}
_INK = "#1A1A1A"
_MUTED = "#5A5A5A"
_WET_GUIDE = "#2A7A72"
_ENTRY = "#C45C26"
_ROAD = "#4A6FA5"
_STAIR = "#333333"
_ACCESS = "#6B4C9A"
_BG = "#F7F5F0"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _fill_for(placement: RoomPlacement) -> str:
    cat = (placement.category or "other").lower()
    return _CATEGORY_FILL.get(cat, _CATEGORY_FILL["other"])


def _render_room(
    placement: RoomPlacement,
    oy: float,
    *,
    target_area: float | None = None,
) -> str:
    r = placement.rect
    fill = _fill_for(placement)
    is_stair = placement.room_id.startswith("stair-") or (
        (placement.category or "") == "circulation" and "楼梯" in (placement.name or "")
    )
    stroke = _STAIR if is_stair else _INK
    sw = 0.08 if is_stair else 0.04
    cx = r.x + r.width / 2
    cy = oy + r.y + r.depth / 2
    name = _esc(placement.name or placement.room_id)
    rid = _esc(placement.room_id)
    area = f"{r.area:.1f}㎡"
    if target_area is not None:
        area = f"{r.area:.1f}/{target_area:.0f}㎡"
    show_detail = r.width >= 1.4 and r.depth >= 1.2
    lines = [
        f'<rect x="{r.x:.3f}" y="{oy + r.y:.3f}" width="{r.width:.3f}" '
        f'height="{r.depth:.3f}" fill="{fill}" fill-opacity="0.9" '
        f'stroke="{stroke}" stroke-width="{sw:.3f}"/>',
        f'<text x="{cx:.3f}" y="{cy - (0.28 if show_detail else 0):.3f}" '
        f'font-size="0.30" fill="{_INK}" text-anchor="middle" '
        f'font-family="Segoe UI, sans-serif">{name}</text>',
    ]
    if show_detail:
        lines.append(
            f'<text x="{cx:.3f}" y="{cy:.3f}" font-size="0.22" '
            f'fill="{_MUTED}" text-anchor="middle" '
            f'font-family="Consolas, monospace">{rid}</text>'
        )
        lines.append(
            f'<text x="{cx:.3f}" y="{cy + 0.28:.3f}" font-size="0.24" '
            f'fill="{_MUTED}" text-anchor="middle" '
            f'font-family="Consolas, monospace">{area}</text>'
        )
    return "\n".join(lines)


def _wet_overlay(
    floor: FloorLayout,
    oy: float,
    *,
    stacks: list | None = None,
) -> str:
    x0 = x1 = y0 = y1 = None
    if stacks:
        a = stacks[0].anchor_rect
        x0, y0 = a.x, a.y
        x1, y1 = a.x + a.width, a.y + a.depth
    elif floor.wet_zone_x0 is not None and floor.wet_zone_x1 is not None:
        x0, x1 = floor.wet_zone_x0, floor.wet_zone_x1
        y0 = floor.wet_zone_y0 if floor.wet_zone_y0 is not None else 0.0
        y1 = floor.wet_zone_y1 if floor.wet_zone_y1 is not None else y0
    if x0 is None or x1 is None or y0 is None or y1 is None:
        return ""
    w = max(0.0, x1 - x0)
    d = max(0.0, y1 - y0)
    if w < 1e-6 or d < 1e-6:
        return ""
    return (
        f'<rect x="{x0:.3f}" y="{oy + y0:.3f}" width="{w:.3f}" height="{d:.3f}" '
        f'fill="none" stroke="{_WET_GUIDE}" stroke-width="0.05" '
        f'stroke-dasharray="0.2 0.12"/>'
        f'<text x="{x0 + 0.1:.3f}" y="{oy + y0 + 0.35:.3f}" font-size="0.22" '
        f'fill="{_WET_GUIDE}" font-family="Consolas, monospace">WS</text>'
    )


def _edge_segment(
    edge: CardinalEdge | str,
    *,
    w: float,
    d: float,
    oy: float,
    inset: float = 0.0,
) -> tuple[float, float, float, float]:
    """返回贴边线段 (x1,y1,x2,y2)，y 含楼层偏移 oy。"""
    key = edge.value if isinstance(edge, CardinalEdge) else str(edge).lower()
    if key == "north":
        return inset, oy + inset, w - inset, oy + inset
    if key == "south":
        return inset, oy + d - inset, w - inset, oy + d - inset
    if key == "west":
        return inset, oy + inset, inset, oy + d - inset
    return w - inset, oy + inset, w - inset, oy + d - inset


def _site_overlays(
    candidate: LayoutCandidate,
    *,
    floor_width: float,
    floor_depth: float,
    oy: float,
    site: SiteSpec | None,
    floor_index: int,
) -> str:
    parts: list[str] = []
    if site is not None:
        # 临路边
        for edge in site.road_edges or []:
            x1, y1, x2, y2 = _edge_segment(
                edge, w=floor_width, d=floor_depth, oy=oy, inset=0.12
            )
            parts.append(
                f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
                f'stroke="{_ROAD}" stroke-width="0.14" stroke-dasharray="0.25 0.12"/>'
            )
        # 入口边高亮（仅地面层）
        if floor_index == 0:
            edge = (
                candidate.exterior_entry.edge
                if candidate.exterior_entry is not None
                else site.entrance_edge
            )
            x1, y1, x2, y2 = _edge_segment(
                edge, w=floor_width, d=floor_depth, oy=oy, inset=0.05
            )
            parts.append(
                f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
                f'stroke="{_ENTRY}" stroke-width="0.18"/>'
            )

    entry = candidate.exterior_entry
    if entry is not None and floor_index == 0:
        parts.append(
            f'<circle cx="{entry.x:.3f}" cy="{oy + entry.y:.3f}" r="0.22" '
            f'fill="{_ENTRY}" stroke="{_INK}" stroke-width="0.03"/>'
        )
        parts.append(
            f'<text x="{entry.x + 0.3:.3f}" y="{oy + entry.y + 0.08:.3f}" '
            f'font-size="0.24" fill="{_ENTRY}" '
            f'font-family="Consolas, monospace">ENTRY</text>'
        )
    return "\n".join(parts)


def _access_overlays(
    floor: FloorLayout,
    oy: float,
    access_graph: AccessGraph | None,
) -> str:
    """应连通虚线：同层 AccessGraph 开口边，连房间中心。"""
    if access_graph is None:
        return ""
    by_id = {p.room_id: p for p in floor.placements}
    opening = {
        SpaceConnectionType.OPEN,
        SpaceConnectionType.DOOR,
        SpaceConnectionType.PASSAGE,
    }
    parts: list[str] = []
    for conn in access_graph.connections:
        if conn.type not in opening:
            continue
        a = by_id.get(conn.a)
        b = by_id.get(conn.b)
        if a is None or b is None:
            continue
        ax = a.rect.x + a.rect.width / 2
        ay = oy + a.rect.y + a.rect.depth / 2
        bx = b.rect.x + b.rect.width / 2
        by = oy + b.rect.y + b.rect.depth / 2
        sw = 0.07 if conn.required else 0.045
        dash = "0.18 0.12" if conn.required else "0.12 0.16"
        parts.append(
            f'<line x1="{ax:.3f}" y1="{ay:.3f}" x2="{bx:.3f}" y2="{by:.3f}" '
            f'stroke="{_ACCESS}" stroke-width="{sw:.3f}" '
            f'stroke-dasharray="{dash}" opacity="0.85"/>'
        )
    return "\n".join(parts)


def _north_arrow(
    *,
    x: float,
    y: float,
    north_angle: float,
) -> str:
    """
    指北针：箭头默认朝 model -Y（图上方 = model north）。
    标注 north_angle；世界北相对 model north 的旋转。
    """
    # 箭头指向图上方（model north）
    return (
        f'<g transform="translate({x:.3f},{y:.3f})">'
        f'<line x1="0" y1="0.25" x2="0" y2="-0.45" stroke="{_INK}" stroke-width="0.05"/>'
        f'<polygon points="0,{-0.55:.3f} -0.18,-0.28 0.18,-0.28" fill="{_INK}"/>'
        f'<text x="0.28" y="-0.35" font-size="0.28" fill="{_INK}" '
        f'font-family="Consolas, monospace">N</text>'
        f'<text x="-0.1" y="0.55" font-size="0.22" fill="{_MUTED}" '
        f'font-family="Consolas, monospace">∠{north_angle:.0f}°</text>'
        f"</g>"
    )


def _legend(x: float, y: float) -> str:
    items = [
        ("public", "公共/DAY"),
        ("private", "私密/NIGHT"),
        ("wet", "湿区"),
        ("service", "服务"),
        ("circulation", "交通/楼梯"),
    ]
    parts = [
        f'<text x="{x:.3f}" y="{y:.3f}" font-size="0.32" fill="{_MUTED}" '
        f'font-family="Segoe UI, sans-serif">图例</text>'
    ]
    for i, (cat, label) in enumerate(items):
        yy = y + 0.45 + i * 0.4
        fill = _CATEGORY_FILL[cat]
        parts.append(
            f'<rect x="{x:.3f}" y="{yy - 0.22:.3f}" width="0.35" height="0.28" '
            f'fill="{fill}" stroke="{_INK}" stroke-width="0.02"/>'
        )
        parts.append(
            f'<text x="{x + 0.5:.3f}" y="{yy:.3f}" font-size="0.28" fill="{_INK}" '
            f'font-family="Segoe UI, sans-serif">{_esc(label)}</text>'
        )
    return "\n".join(parts)


def render_candidate_svg(
    candidate: LayoutCandidate,
    *,
    floor_width: float,
    floor_depth: float,
    floor_labels: dict[str, str] | None = None,
    target_areas: dict[str, float] | None = None,
    site: SiteSpec | None = None,
    access_graph: AccessGraph | None = None,
) -> str:
    """渲染单个候选：各层纵向堆叠 + 场地/入口/通行 debug 叠加。"""
    labels = floor_labels or {}
    targets = target_areas or {}
    gap = 1.0
    n = len(candidate.floors)
    stack_h = n * floor_depth + max(0, n - 1) * gap

    valid = candidate.validation.valid if candidate.validation else None
    hard_n = (
        len(candidate.validation.hard_violations) if candidate.validation else 0
    )
    soft_n = (
        len(candidate.validation.soft_violations) if candidate.validation else 0
    )
    score = candidate.score
    score_s = f"{score:.1f}" if score is not None else "—"
    valid_s = "valid" if valid else ("invalid" if valid is False else "unchecked")
    north_angle = float(getattr(site, "north_angle", 0.0) or 0.0) if site else 0.0

    header_lines = [
        f"seed={candidate.seed}  score={score_s}  {valid_s}",
        f"hard={hard_n}  soft={soft_n}  id={candidate.id}",
        f"north_angle={north_angle:.0f}°",
    ]
    if candidate.exterior_entry is not None:
        e = candidate.exterior_entry
        header_lines.append(
            f"entry={e.edge.value}  on_road={e.on_road_edge}  "
            f"@({e.x:.1f},{e.y:.1f})"
        )
    if access_graph is not None:
        header_lines.append(
            f"access_edges={len(access_graph.connections)}  "
            f"required={len(access_graph.required_connections())}"
        )
    if candidate.metrics:
        bits = []
        for key in (
            "area_accuracy",
            "stair_alignment",
            "wet_stack_alignment",
            "entry_on_road",
            "garage_on_road",
            "access_pref_satisfaction",
            "compactness",
        ):
            if key in candidate.metrics:
                val = candidate.metrics[key]
                if isinstance(val, float):
                    bits.append(f"{key}={val:.3f}")
                else:
                    bits.append(f"{key}={val}")
        if bits:
            header_lines.append("  ".join(bits))

    if candidate.validation and candidate.validation.hard_violations:
        for v in candidate.validation.hard_violations[:6]:
            header_lines.append(f"! {_esc(v.constraint_id)}: {_esc(v.message)}")

    margin_l, margin_r, margin_t, margin_b = 1.2, 3.5, 1.6, 0.8
    header_h = 0.4 * len(header_lines) + 0.2
    margin_t = max(margin_t, header_h + 0.4)

    vb_w = floor_width + margin_l + margin_r
    vb_h = stack_h + margin_t + margin_b

    body: list[str] = [
        f'<rect x="{-margin_l:.3f}" y="{-margin_t:.3f}" width="{vb_w:.3f}" '
        f'height="{vb_h:.3f}" fill="{_BG}"/>'
    ]

    for i, line in enumerate(header_lines):
        body.append(
            f'<text x="0" y="{-margin_t + 0.35 + i * 0.4:.3f}" font-size="0.32" '
            f'fill="{_INK}" font-family="Consolas, monospace">{line}</text>'
        )

    body.append(
        _north_arrow(x=floor_width + 1.4, y=0.9, north_angle=north_angle)
    )

    for i, floor in enumerate(candidate.floors):
        oy = i * (floor_depth + gap)
        label = labels.get(floor.floor_id, floor.floor_id)
        core = floor.core_placement or "—"
        body.append(
            f'<text x="0.1" y="{oy + 0.35:.3f}" font-size="0.36" fill="{_INK}" '
            f'font-family="Segoe UI, sans-serif" font-weight="700">'
            f'{_esc(label)} · core={_esc(core)}</text>'
        )
        body.append(
            f'<rect x="0" y="{oy:.3f}" width="{floor_width:.3f}" '
            f'height="{floor_depth:.3f}" fill="#fff" stroke="{_INK}" '
            f'stroke-width="0.08"/>'
        )
        for p in floor.placements:
            body.append(
                _render_room(p, oy, target_area=targets.get(p.room_id))
            )
        body.append(_wet_overlay(floor, oy, stacks=candidate.wet_stacks))
        body.append(
            _site_overlays(
                candidate,
                floor_width=floor_width,
                floor_depth=floor_depth,
                oy=oy,
                site=site,
                floor_index=i,
            )
        )
        body.append(_access_overlays(floor, oy, access_graph))

    body.append(_legend(floor_width + 0.4, 1.6))

    body.append(
        f'<text x="{floor_width / 2:.3f}" y="{stack_h + 0.4:.3f}" '
        f'font-size="0.28" fill="{_MUTED}" text-anchor="middle" '
        f'font-family="Consolas, monospace">'
        f'{floor_width:.1f} × {floor_depth:.1f} m</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{-margin_l:.3f} {-margin_t:.3f} {vb_w:.3f} {vb_h:.3f}">\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def write_candidate_svg(
    candidate: LayoutCandidate,
    path: Path | str,
    *,
    floor_width: float,
    floor_depth: float,
    floor_labels: dict[str, str] | None = None,
    target_areas: dict[str, float] | None = None,
    site: SiteSpec | None = None,
    access_graph: AccessGraph | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = render_candidate_svg(
        candidate,
        floor_width=floor_width,
        floor_depth=floor_depth,
        floor_labels=floor_labels,
        target_areas=target_areas,
        site=site,
        access_graph=access_graph,
    )
    path.write_text(svg, encoding="utf-8")
    return path

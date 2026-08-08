"""
将 LayoutCandidate 渲染为 SVG（米坐标 = SVG 用户单位）。

y=0 为北（图上方），与 solver 几何一致。
"""

from __future__ import annotations

import html
from pathlib import Path

from packages.schema.layout import FloorLayout, LayoutCandidate, RoomPlacement

# 浅色调试色板（按 category）
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
        f'stroke="{_INK}" stroke-width="0.04"/>',
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


def _wet_overlay(floor: FloorLayout, oy: float) -> str:
    if floor.wet_zone_x0 is None or floor.wet_zone_x1 is None:
        return ""
    x0, x1 = floor.wet_zone_x0, floor.wet_zone_x1
    y0 = floor.wet_zone_y0 if floor.wet_zone_y0 is not None else 0.0
    y1 = floor.wet_zone_y1 if floor.wet_zone_y1 is not None else y0
    w = max(0.0, x1 - x0)
    d = max(0.0, y1 - y0)
    if w < 1e-6 or d < 1e-6:
        return ""
    return (
        f'<rect x="{x0:.3f}" y="{oy + y0:.3f}" width="{w:.3f}" height="{d:.3f}" '
        f'fill="none" stroke="{_WET_GUIDE}" stroke-width="0.05" '
        f'stroke-dasharray="0.2 0.12"/>'
    )


def _legend(x: float, y: float) -> str:
    items = [
        ("public", "公共"),
        ("private", "私密"),
        ("wet", "湿区"),
        ("service", "服务"),
        ("circulation", "交通"),
    ]
    parts = [f'<text x="{x:.3f}" y="{y:.3f}" font-size="0.32" fill="{_MUTED}" '
             f'font-family="Segoe UI, sans-serif">图例</text>']
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
) -> str:
    """渲染单个候选：各层纵向堆叠 + 元数据页眉。"""
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

    header_lines = [
        f"seed={candidate.seed}  score={score_s}  {valid_s}",
        f"hard={hard_n}  soft={soft_n}  id={candidate.id}",
    ]
    if candidate.metrics:
        bits = []
        for key in (
            "area_accuracy",
            "stair_alignment",
            "wet_zone_alignment",
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

    margin_l, margin_r, margin_t, margin_b = 1.2, 3.2, 1.6, 0.6
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
        body.append(_wet_overlay(floor, oy))

    body.append(_legend(floor_width + 0.4, 0.2))

    # 尺寸标注
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
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = render_candidate_svg(
        candidate,
        floor_width=floor_width,
        floor_depth=floor_depth,
        floor_labels=floor_labels,
        target_areas=target_areas,
    )
    path.write_text(svg, encoding="utf-8")
    return path

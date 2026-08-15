"""
将 LayoutCandidate 渲染为 SVG（米坐标 = SVG 用户单位）。

y=0 为 model north（图上方），与 solver 几何一致。
Debug 叠加：north_angle、入口、临路、StairCore、WetStack、Atrium/Skylight。
"""

from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path
from typing import Literal

from packages.schema.layout import DoorOpening, FloorLayout, LayoutCandidate, RoomPlacement, WindowOpening
from packages.schema.site import CardinalEdge, SiteSpec
from packages.schema.topology import AccessGraph, SpaceConnectionType
from packages.schema.vertical_void import VerticalVoidType

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
_DOOR = "#8B4513"
_WINDOW = "#1D6FA5"
_BG = "#F7F5F0"
_ATRIUM_FILL = "#D4EAF2"
_ATRIUM_STROKE = "#2E6B8A"
_SKYLIGHT = "#D4940A"

RenderMode = Literal["debug", "customer"]


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _fill_for(placement: RoomPlacement) -> str:
    if placement.room_id.startswith("void-"):
        return _ATRIUM_FILL
    cat = (placement.category or "other").lower()
    return _CATEGORY_FILL.get(cat, _CATEGORY_FILL["other"])


def _render_room(
    placement: RoomPlacement,
    oy: float,
    *,
    target_area: float | None = None,
    render_mode: RenderMode = "customer",
) -> str:
    r = placement.rect
    fill = _fill_for(placement)
    is_void = placement.room_id.startswith("void-")
    is_stair = placement.room_id.startswith("stair-") or (
        (placement.category or "") == "circulation" and "楼梯" in (placement.name or "")
    )
    if is_void:
        stroke = _ATRIUM_STROKE
        sw = 0.06
        dash = ' stroke-dasharray="0.18 0.10"'
        fill_opacity = "0.55"
    elif is_stair:
        stroke = _STAIR
        sw = 0.08
        dash = ""
        fill_opacity = "0.9"
    else:
        stroke = _INK
        sw = 0.04
        dash = ""
        fill_opacity = "0.9"
    cx = r.x + r.width / 2
    cy = oy + r.y + r.depth / 2
    name = _esc(placement.name or placement.room_id)
    rid = _esc(placement.room_id)
    area = f"{r.area:.1f}㎡"
    if target_area is not None:
        area = f"{r.area:.1f}/{target_area:.0f}㎡"
    show_detail = r.width >= 1.4 and r.depth >= 1.2
    # 成组便于桌面拖拽时 rect+label 一起平移
    lines = [
        f'<g class="room-node" data-room-id="{rid}">',
        f'<rect class="room-shape" data-room-id="{rid}" x="{r.x:.3f}" y="{oy + r.y:.3f}" width="{r.width:.3f}" '
        f'height="{r.depth:.3f}" fill="{fill}" fill-opacity="{fill_opacity}" '
        f'stroke="{stroke}" stroke-width="{sw:.3f}"{dash}/>',
        f'<text x="{cx:.3f}" y="{cy - (0.28 if show_detail else 0):.3f}" '
        f'font-size="0.30" fill="{_INK}" text-anchor="middle" '
        f'font-family="Segoe UI, sans-serif">{name}</text>',
    ]
    if show_detail:
        if render_mode == "debug":
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
    lines.append("</g>")
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


def _skylight_void_ids_on_floor(
    candidate: LayoutCandidate,
    floor_id: str,
) -> set[str]:
    """顶层天窗标注：同一 atrium void 仅在 span 最高层显示。"""
    by_void: dict[str, list] = defaultdict(list)
    for vp in candidate.vertical_void_placements:
        if vp.void_type != VerticalVoidType.ATRIUM or not vp.skylight_required:
            continue
        by_void[vp.void_id].append(vp)
    if not by_void:
        return set()
    floor_order = {f.floor_id: i for i, f in enumerate(candidate.floors)}
    on_floor: set[str] = set()
    for void_id, placements in by_void.items():
        top = max(placements, key=lambda vp: floor_order.get(vp.floor_id, -1))
        if top.floor_id == floor_id:
            on_floor.add(void_id)
    return on_floor


def _skylight_marker(x: float, y: float, *, size: float = 0.28) -> str:
    """简易天窗符号：圆 + 射线。"""
    r = size * 0.45
    rays = []
    for i in range(8):
        ang = i * 45
        rays.append(
            f'<line x1="{x:.3f}" y1="{y:.3f}" '
            f'x2="{x + size * 0.9:.3f}" y2="{y:.3f}" '
            f'stroke="{_SKYLIGHT}" stroke-width="0.03" '
            f'transform="rotate({ang} {x:.3f} {y:.3f})"/>'
        )
    return (
        f'<g class="skylight-marker" data-kind="skylight">'
        f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r:.3f}" '
        f'fill="{_SKYLIGHT}" fill-opacity="0.85" stroke="{_INK}" stroke-width="0.02"/>'
        + "".join(rays)
        + f'<text x="{x:.3f}" y="{y + size * 1.1:.3f}" font-size="0.20" '
        f'fill="{_SKYLIGHT}" text-anchor="middle" '
        f'font-family="Consolas, monospace">天窗</text>'
        f"</g>"
    )


def _atrium_void_overlay(
    candidate: LayoutCandidate,
    floor: FloorLayout,
    oy: float,
    *,
    render_mode: RenderMode = "customer",
) -> str:
    """天井叠加：debug 画虚线框 + ATRIUM 标签；customer 仅保留天窗符号。"""
    voids = [
        vp
        for vp in candidate.vertical_void_placements
        if vp.floor_id == floor.floor_id and vp.void_type == VerticalVoidType.ATRIUM
    ]
    if not voids:
        return ""
    skylight_ids = _skylight_void_ids_on_floor(candidate, floor.floor_id)
    parts: list[str] = []
    for vp in voids:
        r = vp.rect
        if render_mode == "debug":
            parts.append(
                f'<rect x="{r.x:.3f}" y="{oy + r.y:.3f}" width="{r.width:.3f}" '
                f'height="{r.depth:.3f}" fill="none" stroke="{_ATRIUM_STROKE}" '
                f'stroke-width="0.07" stroke-dasharray="0.22 0.12" '
                f'data-void-id="{_esc(vp.void_id)}"/>'
            )
            parts.append(
                f'<text x="{r.x + 0.12:.3f}" y="{oy + r.y + 0.38:.3f}" '
                f'font-size="0.22" fill="{_ATRIUM_STROKE}" '
                f'font-family="Consolas, monospace">ATRIUM</text>'
            )
        if vp.void_id in skylight_ids:
            cx = r.x + r.width / 2
            cy = oy + r.y + r.depth / 2
            parts.append(_skylight_marker(cx, cy))
    return "\n".join(parts)


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
    render_mode: RenderMode = "customer",
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
        entry_label = "ENTRY" if render_mode == "debug" else "入口"
        parts.append(
            f'<circle cx="{entry.x:.3f}" cy="{oy + entry.y:.3f}" r="0.22" '
            f'fill="{_ENTRY}" stroke="{_INK}" stroke-width="0.03"/>'
        )
        parts.append(
            f'<text x="{entry.x + 0.3:.3f}" y="{oy + entry.y + 0.08:.3f}" '
            f'font-size="0.24" fill="{_ENTRY}" '
            f'font-family="{"Consolas, monospace" if render_mode == "debug" else "Segoe UI, sans-serif"}">'
            f'{entry_label}</text>'
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


def _door_overlays(floor: FloorLayout, oy: float, openings: list[DoorOpening]) -> str:
    """Phase 2.2：门洞线段 + 开启弧（不改几何）。"""
    parts: list[str] = []
    for op in openings:
        if op.floor_id != floor.floor_id:
            continue
        half = op.width / 2
        if op.axis == "y":
            # 竖墙：洞口沿 y
            x = op.x
            y0 = oy + op.y - half
            y1 = oy + op.y + half
            parts.append(
                f'<line x1="{x:.3f}" y1="{y0:.3f}" x2="{x:.3f}" y2="{y1:.3f}" '
                f'stroke="{_DOOR}" stroke-width="0.12"/>'
            )
        else:
            y = oy + op.y
            x0 = op.x - half
            x1 = op.x + half
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y:.3f}" x2="{x1:.3f}" y2="{y:.3f}" '
                f'stroke="{_DOOR}" stroke-width="0.12"/>'
            )

        if op.connection_type == "open":
            continue
        if op.hinge_x is None or op.hinge_y is None or op.swing_room_id is None:
            continue

        hx, hy = op.hinge_x, oy + op.hinge_y
        # 门扇：从铰链到洞口另一端
        if op.axis == "y":
            other_y = oy + op.y + (half if op.hinge_y <= op.y else -half)
            leaf_x2, leaf_y2 = hx, other_y
        else:
            other_x = op.x + (half if op.hinge_x <= op.x else -half)
            leaf_x2, leaf_y2 = other_x, hy

        # 开启 90°：门扇端点绕铰链旋入 swing 侧
        swing_p = next(
            (p for p in floor.placements if p.room_id == op.swing_room_id), None
        )
        if swing_p is None:
            continue
        scx = swing_p.rect.x + swing_p.rect.width / 2
        scy = oy + swing_p.rect.y + swing_p.rect.depth / 2

        # 关闭位置向量 → 旋向 swing 中心的一侧
        dx = leaf_x2 - hx
        dy = leaf_y2 - hy
        # 两个垂直方向
        px, py = -dy, dx
        qx, qy = dy, -dx
        # 选更靠近 swing 中心的法向作为开启方向
        to_s = (scx - hx, scy - hy)
        if px * to_s[0] + py * to_s[1] >= qx * to_s[0] + qy * to_s[1]:
            open_x, open_y = hx + px, hy + py
        else:
            open_x, open_y = hx + qx, hy + qy

        parts.append(
            f'<line x1="{hx:.3f}" y1="{hy:.3f}" x2="{open_x:.3f}" y2="{open_y:.3f}" '
            f'stroke="{_DOOR}" stroke-width="0.06"/>'
        )
        # 简易四分之一弧：用二次近似 path
        r = op.width
        parts.append(
            f'<path d="M {leaf_x2:.3f} {leaf_y2:.3f} '
            f'A {r:.3f} {r:.3f} 0 0 1 {open_x:.3f} {open_y:.3f}" '
            f'fill="none" stroke="{_DOOR}" stroke-width="0.04" '
            f'stroke-dasharray="0.08 0.06" opacity="0.75"/>'
        )
        parts.append(
            f'<circle cx="{hx:.3f}" cy="{hy:.3f}" r="0.06" fill="{_DOOR}"/>'
        )
    return "\n".join(parts)


def _window_overlays(
    floor: FloorLayout,
    oy: float,
    openings: list[WindowOpening],
) -> str:
    """外窗符号：墙线上的开口端点 + 平行玻璃线（区别于门扇弧线）。"""
    parts: list[str] = []
    for w in openings:
        if w.floor_id != floor.floor_id:
            continue
        half = w.width / 2
        if w.axis == "x":
            x0, x1 = w.x - half, w.x + half
            y = oy + w.y
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y:.3f}" x2="{x1:.3f}" y2="{y:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.10"/>'
            )
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y - 0.07:.3f}" x2="{x0:.3f}" y2="{y + 0.07:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.05"/>'
            )
            parts.append(
                f'<line x1="{x1:.3f}" y1="{y - 0.07:.3f}" x2="{x1:.3f}" y2="{y + 0.07:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.05"/>'
            )
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y - 0.03:.3f}" x2="{x1:.3f}" y2="{y - 0.03:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.035"/>'
            )
            parts.append(
                f'<line x1="{x0:.3f}" y1="{y + 0.03:.3f}" x2="{x1:.3f}" y2="{y + 0.03:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.035"/>'
            )
        else:
            y0, y1 = oy + w.y - half, oy + w.y + half
            x = w.x
            parts.append(
                f'<line x1="{x:.3f}" y1="{y0:.3f}" x2="{x:.3f}" y2="{y1:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.10"/>'
            )
            parts.append(
                f'<line x1="{x - 0.07:.3f}" y1="{y0:.3f}" x2="{x + 0.07:.3f}" y2="{y0:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.05"/>'
            )
            parts.append(
                f'<line x1="{x - 0.07:.3f}" y1="{y1:.3f}" x2="{x + 0.07:.3f}" y2="{y1:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.05"/>'
            )
            parts.append(
                f'<line x1="{x - 0.03:.3f}" y1="{y0:.3f}" x2="{x - 0.03:.3f}" y2="{y1:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.035"/>'
            )
            parts.append(
                f'<line x1="{x + 0.03:.3f}" y1="{y0:.3f}" x2="{x + 0.03:.3f}" y2="{y1:.3f}" '
                f'stroke="{_WINDOW}" stroke-width="0.035"/>'
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
    render_mode: RenderMode = "customer",
) -> str:
    """渲染单个候选：各层纵向堆叠；customer 为交付视图，debug 含工程师核查叠加。"""
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
    if candidate.door_openings:
        header_lines.append(f"doors={len(candidate.door_openings)}")
    if candidate.vertical_void_placements:
        atrium_n = sum(
            1
            for vp in candidate.vertical_void_placements
            if vp.void_type == VerticalVoidType.ATRIUM
        )
        skylight_n = sum(
            1
            for vp in candidate.vertical_void_placements
            if vp.void_type == VerticalVoidType.ATRIUM and vp.skylight_required
        )
        header_lines.append(f"atrium_voids={atrium_n}  skylight={skylight_n > 0}")
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
        body.append(
            _floor_stack_label(floor, label=label, oy=oy)
        )
        body.extend(
            _render_floor_geometry(
                candidate,
                floor,
                floor_index=i,
                oy=oy,
                floor_width=floor_width,
                floor_depth=floor_depth,
                targets=targets,
                site=site,
                access_graph=access_graph,
                render_mode=render_mode,
            )
        )

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


def render_floor_svg(
    candidate: LayoutCandidate,
    floor_id: str,
    *,
    floor_width: float,
    floor_depth: float,
    floor_labels: dict[str, str] | None = None,
    target_areas: dict[str, float] | None = None,
    site: SiteSpec | None = None,
    access_graph: AccessGraph | None = None,
    render_mode: RenderMode = "customer",
) -> str:
    """渲染单层平面 SVG（报告 / 分层消费）；不做 DOM 裁剪整图。"""
    labels = floor_labels or {}
    targets = target_areas or {}
    floor_index, floor = _find_floor(candidate, floor_id)
    label = labels.get(floor.floor_id, floor.floor_id)
    north_angle = float(getattr(site, "north_angle", 0.0) or 0.0) if site else 0.0

    header_lines = [
        f"{_esc(label)}  seed={candidate.seed}  id={_esc(candidate.id)}",
        f"core={_esc(floor.core_placement or '—')}  north_angle={north_angle:.0f}°",
    ]

    margin_l, margin_r, margin_t, margin_b = 1.2, 3.5, 1.4, 0.8
    header_h = 0.4 * len(header_lines) + 0.2
    margin_t = max(margin_t, header_h + 0.4)
    vb_w = floor_width + margin_l + margin_r
    vb_h = floor_depth + margin_t + margin_b
    oy = 0.0

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
    body.extend(
        _render_floor_geometry(
            candidate,
            floor,
            floor_index=floor_index,
            oy=oy,
            floor_width=floor_width,
            floor_depth=floor_depth,
            targets=targets,
            site=site,
            access_graph=access_graph,
            render_mode=render_mode,
        )
    )
    body.append(_legend(floor_width + 0.4, 1.6))
    body.append(
        f'<text x="{floor_width / 2:.3f}" y="{floor_depth + 0.4:.3f}" '
        f'font-size="0.28" fill="{_MUTED}" text-anchor="middle" '
        f'font-family="Consolas, monospace">'
        f'{floor_width:.1f} × {floor_depth:.1f} m</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'data-floor-id="{_esc(floor.floor_id)}" '
        f'viewBox="{-margin_l:.3f} {-margin_t:.3f} {vb_w:.3f} {vb_h:.3f}">\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def _find_floor(
    candidate: LayoutCandidate, floor_id: str
) -> tuple[int, FloorLayout]:
    for i, floor in enumerate(candidate.floors):
        if floor.floor_id == floor_id:
            return i, floor
    known = ", ".join(f.floor_id for f in candidate.floors) or "(none)"
    raise ValueError(f"floor_id 不存在：{floor_id}；已知：{known}")


def _floor_stack_label(floor: FloorLayout, *, label: str, oy: float) -> str:
    core = floor.core_placement or "—"
    return (
        f'<text x="0.1" y="{oy + 0.35:.3f}" font-size="0.36" fill="{_INK}" '
        f'font-family="Segoe UI, sans-serif" font-weight="700">'
        f'{_esc(label)} · core={_esc(core)}</text>'
    )


def _render_floor_geometry(
    candidate: LayoutCandidate,
    floor: FloorLayout,
    *,
    floor_index: int,
    oy: float,
    floor_width: float,
    floor_depth: float,
    targets: dict[str, float],
    site: SiteSpec | None,
    access_graph: AccessGraph | None,
    render_mode: RenderMode = "customer",
) -> list[str]:
    parts: list[str] = [
        f'<rect x="0" y="{oy:.3f}" width="{floor_width:.3f}" '
        f'height="{floor_depth:.3f}" fill="#fff" stroke="{_INK}" '
        f'stroke-width="0.08"/>'
    ]
    for p in floor.placements:
        parts.append(
            _render_room(
                p,
                oy,
                target_area=targets.get(p.room_id),
                render_mode=render_mode,
            )
        )
    if render_mode == "debug":
        parts.append(_wet_overlay(floor, oy, stacks=candidate.wet_stacks))
    atrium = _atrium_void_overlay(
        candidate, floor, oy, render_mode=render_mode
    )
    if atrium.strip():
        parts.append(
            f'<g class="derived-overlay" data-kind="atrium">{atrium}</g>'
        )
    parts.append(
        _site_overlays(
            candidate,
            floor_width=floor_width,
            floor_depth=floor_depth,
            oy=oy,
            site=site,
            floor_index=floor_index,
            render_mode=render_mode,
        )
    )
    access = _access_overlays(floor, oy, access_graph)
    if access.strip():
        parts.append(f'<g class="derived-overlay" data-kind="access">{access}</g>')
    doors = _door_overlays(floor, oy, candidate.door_openings)
    if doors.strip():
        parts.append(f'<g class="derived-overlay" data-kind="doors">{doors}</g>')
    windows = _window_overlays(floor, oy, floor.window_openings)
    if windows.strip():
        parts.append(f'<g class="derived-overlay" data-kind="windows">{windows}</g>')
    return parts


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
    render_mode: RenderMode = "customer",
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
        render_mode=render_mode,
    )
    path.write_text(svg, encoding="utf-8")
    return path

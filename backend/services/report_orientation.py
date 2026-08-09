"""报告平面朝向 — 只投影已有 SiteCoordinateSystem 事实，不另发明坐标系。

约定（与 solver/geometry/site_coords.py 一致）：
  图上方 = model north（−Y）
  north_angle = 正北相对 model north 外向的顺时针角（度）
  north_angle=0 → 世界北 = 图上方
  north_angle=90 → 世界北 = 图左（model west）

HTML/CSS：默认北针箭头朝上；世界北 = rotate(-north_angle)。
"""

from __future__ import annotations

from typing import Any


def normalize_north_angle_deg(degrees: float) -> float:
    return float(degrees) % 360.0


def north_arrow_css_rotation_deg(north_angle_deg: float) -> float:
    """默认箭头朝 model north（屏上向上）时，指向世界北的 CSS rotate 角度。"""
    return -normalize_north_angle_deg(north_angle_deg)


def resolve_north_angle_deg(
    requirement_spec: dict[str, Any] | None,
    program: dict[str, Any] | None = None,
) -> float | None:
    """
    解析报告用 north_angle。

    - requirement_spec.site.north_angle 为数字（含 0）→ 已知
    - 显式 null → 未知（不画北针）
    - 仅有 normalize 写入的 assumption site.north_angle → 按假设值（通常 0）
    - 否则不把 program 默认 0 当成「已知正北」（避免假 ↑N）
    """
    if isinstance(requirement_spec, dict):
        site = requirement_spec.get("site")
        if isinstance(site, dict) and "north_angle" in site:
            raw = site.get("north_angle")
            if raw is None:
                return None
            if isinstance(raw, (int, float)):
                return normalize_north_angle_deg(float(raw))
            return None
        for a in requirement_spec.get("assumptions") or []:
            if not isinstance(a, dict) or a.get("key") != "site.north_angle":
                continue
            val = a.get("value")
            if isinstance(val, (int, float)):
                return normalize_north_angle_deg(float(val))
    # program 仅在显式给出非默认语义时使用：有 site.north_angle 字段且调用方
    # 已通过 requirement 表达未知时不会走到这里的「site 键缺失」分支误用。
    # 缺 requirement site.north_angle 且无 assumption → 未知。
    _ = program  # 保留参数供 serializer 日后注入；当前不默读 program 默认 0
    return None

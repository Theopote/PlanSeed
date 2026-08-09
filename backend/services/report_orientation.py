"""报告平面朝向 — 只投影已有 SiteCoordinateSystem 事实，不另发明坐标系。

权威链路（Report Renderer 禁止跳过中间层自己读 site）：

  SiteCoordinateSystem / requirement.site.north_angle
        ↓  resolve_north_angle_deg（仅 report_builder）
  FloorPlanBlock.north_angle_deg + orientation_defined
        ↓
  Report HTML（只 rotate / 或显示「北向未定义」）

约定（与 solver/geometry/site_coords.py 一致）：
  图上方 = model north（−Y）
  north_angle = 正北相对 model north 外向的顺时针角（度）
  north_angle=0 → 世界北 = 图上方
  north_angle=90 → 世界北 = 图左（model west）

HTML/CSS：默认北针箭头朝上；世界北 = rotate(-north_angle)。
"""

from __future__ import annotations

from typing import Any

from solver.geometry.site_coords import SiteCoordinateSystem, normalize_azimuth


def normalize_north_angle_deg(degrees: float) -> float:
    return normalize_azimuth(float(degrees))


def north_arrow_css_rotation_deg(north_angle_deg: float) -> float:
    """默认箭头朝 model north（屏上向上）时，指向世界北的 CSS rotate 角度。"""
    rot = -normalize_north_angle_deg(north_angle_deg)
    # 避免 -0.0 写成 rotate(-0.0000deg)
    return 0.0 if abs(rot) < 1e-12 else rot


def resolve_north_angle_deg(
    requirement_spec: dict[str, Any] | None,
    program: dict[str, Any] | None = None,
) -> float | None:
    """
    解析报告用 north_angle（供 builder 写入 FloorPlanBlock；HTML 不得调用）。

    - requirement_spec.site.north_angle 为数字（含 0）→ 已知（经 SiteCoordinateSystem）
    - 显式 null → 未知（不画北针）
    - 仅有 normalize 写入的 assumption site.north_angle → 按假设值
    - 否则不把 program / SiteCoordinateSystem.from_site 默认 0 当成「已知正北」
    """
    if isinstance(requirement_spec, dict):
        site = requirement_spec.get("site")
        if isinstance(site, dict) and "north_angle" in site:
            raw = site.get("north_angle")
            if raw is None:
                return None
            if isinstance(raw, (int, float)):
                return SiteCoordinateSystem(north_angle=float(raw)).north_angle
            return None
        for a in requirement_spec.get("assumptions") or []:
            if not isinstance(a, dict) or a.get("key") != "site.north_angle":
                continue
            val = a.get("value")
            if isinstance(val, (int, float)):
                return SiteCoordinateSystem(north_angle=float(val)).north_angle
    _ = program
    return None

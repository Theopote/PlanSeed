"""场地评价 — setback / envelope，不再使用常量 100。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, PlacementSource
from packages.schema.program import DesignProgram
from solver.geometry.rect import Rect, contains, from_placement


def compute_site_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float | int | bool]:
    """
    setback_compliance：
    - 规划退界未提供（全 0 + unspecified）→ 1.0，并标记 setback_info_provided=False
    - 否则：程序房间落在 buildable envelope 内的比例
    """
    site = program.site
    sb = site.setbacks
    info_provided = site.setback_source == "user" or any(
        v > 0 for v in (sb.north, sb.south, sb.east, sb.west)
    )

    buildable = Rect(
        x=program.buildable.x,
        y=program.buildable.y,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )

    program_placements = [
        p
        for fl in candidate.floors
        for p in fl.placements
        if p.source == PlacementSource.PROGRAM
    ]
    if not program_placements:
        return {
            "setback_compliance": 1.0,
            "setback_info_provided": info_provided,
            "rooms_inside_buildable": 1.0,
        }

    inside = 0
    for p in program_placements:
        if contains(buildable, from_placement(p.rect)):
            inside += 1
    ratio = inside / len(program_placements)

    # 未提供退界信息时：不假装“法规满分”，但 geometry hard 已保证不越界
    # 合规分仍用 envelope 内比例；UI 可用 setback_info_provided 解释
    return {
        "setback_compliance": round(ratio, 4),
        "setback_info_provided": info_provided,
        "rooms_inside_buildable": round(ratio, 4),
    }


def site_score(metrics: dict[str, float | int | bool]) -> float:
    compliance = float(metrics.get("setback_compliance", 1.0))
    base = compliance * 100.0
    # 无规划信息时略降权展示：仍高分但不伪装成“审查通过”
    if not metrics.get("setback_info_provided", False):
        base = min(base, 95.0)
    return max(0.0, min(100.0, base))

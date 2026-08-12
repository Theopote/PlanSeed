"""场地评价 — setback / envelope / 临路软偏好。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, PlacementSource
from packages.schema.program import DesignProgram
from solver.evaluation.orientation import exterior_world_orientations
from solver.geometry.rect import contains, from_placement, program_local_buildable
from solver.geometry.site_coords import SiteCoordinateSystem
from solver.semantics.roles import is_garage


def compute_site_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float | int | bool]:
    """
    setback_compliance + 临路软偏好（非 hard）：
    - entry_on_road：ExteriorEntry 落在 road_edges 上
    - garage_on_road：车库贴临路边外墙
    """
    site = program.site
    sb = site.setbacks
    info_provided = site.setback_source == "user" or any(
        v > 0 for v in (sb.north, sb.south, sb.east, sb.west)
    )

    buildable = program_local_buildable(program)

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
            "entry_on_road": 1.0,
            "garage_on_road": 1.0,
        }

    inside = sum(
        1 for p in program_placements if contains(buildable, from_placement(p.rect))
    )
    ratio = inside / len(program_placements)

    roads = {e.value for e in (site.road_edges or [])}
    entry_on_road = 1.0
    if roads:
        if candidate.exterior_entry is not None:
            entry_on_road = 1.0 if candidate.exterior_entry.on_road_edge else 0.0
        elif site.entrance_edge.value in roads:
            entry_on_road = 1.0
        else:
            entry_on_road = 0.0
    # 无临路信息：不惩罚

    garage_on_road = 1.0
    if roads:
        cs = SiteCoordinateSystem.from_site(site)
        garage_rooms = {r.id for r in program.rooms if is_garage(r)}
        garage_placements = [
            p for p in program_placements if p.room_id in garage_rooms
        ]
        if garage_placements:
            hits = 0
            for p in garage_placements:
                worlds = exterior_world_orientations(
                    from_placement(p.rect), buildable, cs
                )
                if worlds & roads:
                    hits += 1
            garage_on_road = hits / len(garage_placements)

    return {
        "setback_compliance": round(ratio, 4),
        "setback_info_provided": info_provided,
        "rooms_inside_buildable": round(ratio, 4),
        "entry_on_road": float(entry_on_road),
        "garage_on_road": round(float(garage_on_road), 4),
    }


def site_score(metrics: dict[str, float | int | bool]) -> float:
    compliance = float(metrics.get("setback_compliance", 1.0))
    base = compliance * 100.0
    no_setback_info = not metrics.get("setback_info_provided", False)
    if no_setback_info:
        # 无规划退线信息：不假装规范满分
        base = min(base, 95.0)
    # 临路软偏好：轻微加权（非 hard）；不突破无规划信息上限
    entry = float(metrics.get("entry_on_road", 1.0))
    garage = float(metrics.get("garage_on_road", 1.0))
    base = base * 0.9 + (entry * 5.0 + garage * 5.0)
    if no_setback_info:
        base = min(base, 95.0)
    return max(0.0, min(100.0, base))

"""朝向约束评价 — OrientationConstraint 闭环（尊重 north_angle）。"""

from __future__ import annotations

from packages.schema.constraints import ConstraintKind, OrientationConstraint
from packages.schema.layout import LayoutCandidate, Violation
from packages.schema.program import DesignProgram
from packages.schema.site import CardinalOrientation
from solver.geometry.rect import Rect, exterior_edges, from_placement, program_local_buildable
from solver.geometry.site_coords import SiteCoordinateSystem

EDGE_TOLERANCE = 0.05  # m：贴外墙判定


def exterior_model_edges(
    room_rect: Rect,
    buildable: Rect,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> set[str]:
    """房间贴靠的 model 边集合（north/south/east/west，绘图坐标）。"""
    return set(exterior_edges(room_rect, buildable, tolerance=tolerance))


def exterior_world_orientations(
    room_rect: Rect,
    buildable: Rect,
    coords: SiteCoordinateSystem,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> set[str]:
    """
    房间外墙朝向的世界 cardinal 集合。

    preferred_orientation=south 表示世界正南，不是「SVG 下边」。
    """
    model = exterior_model_edges(room_rect, buildable, tolerance=tolerance)
    return {coords.world_orientation_for_edge(edge).value for edge in model}


def exterior_orientations(
    room_rect: Rect,
    buildable: Rect,
    *,
    tolerance: float = EDGE_TOLERANCE,
    north_angle: float = 0.0,
) -> set[str]:
    """
    兼容入口：返回世界朝向集合。

    north_angle=0 时与旧「y=0=北」行为一致。
    """
    coords = SiteCoordinateSystem(north_angle=north_angle)
    return exterior_world_orientations(
        room_rect, buildable, coords, tolerance=tolerance
    )


def _site_coords(program: DesignProgram) -> SiteCoordinateSystem:
    return SiteCoordinateSystem.from_site(program.site)


def _faces_for_placement(
    program: DesignProgram,
    room_rect: Rect,
    buildable: Rect,
) -> set[str]:
    return exterior_world_orientations(
        room_rect, buildable, _site_coords(program)
    )


def compute_orientation_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float | int]:
    """
    评价 OrientationConstraint 满足度（世界朝向 + north_angle）。

    无朝向约束时返回 1.0（不惩罚）。
    """
    constraints = [
        c
        for c in program.constraints
        if c.kind == ConstraintKind.ORIENTATION and isinstance(c, OrientationConstraint)
    ]
    if not constraints:
        return {
            "orientation_satisfaction": 1.0,
            "orientation_constraint_count": 0,
            "orientation_satisfied_count": 0,
            "north_angle": float(program.site.north_angle or 0.0),
        }

    buildable = program_local_buildable(program)
    placement_map = {
        p.room_id: p for fl in candidate.floors for p in fl.placements
    }

    weighted_sat = 0.0
    weight_sum = 0.0
    satisfied_count = 0

    for c in constraints:
        w = c.weight if c.weight > 0 else 1.0
        weight_sum += w
        p = placement_map.get(c.room_id)
        if p is None:
            continue
        faces = _faces_for_placement(program, from_placement(p.rect), buildable)
        preferred = c.preferred_orientation.lower()
        ok = preferred in faces
        if ok:
            satisfied_count += 1
            weighted_sat += w

    satisfaction = weighted_sat / weight_sum if weight_sum > 0 else 1.0
    return {
        "orientation_satisfaction": round(satisfaction, 4),
        "orientation_constraint_count": len(constraints),
        "orientation_satisfied_count": satisfied_count,
        "north_angle": float(program.site.north_angle or 0.0),
    }


def orientation_soft_violations(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[Violation]:
    """未满足的 soft OrientationConstraint → soft violations（可解释）。"""
    buildable = program_local_buildable(program)
    coords = _site_coords(program)
    placement_map = {
        p.room_id: p for fl in candidate.floors for p in fl.placements
    }
    violations: list[Violation] = []

    for c in program.constraints:
        if c.kind != ConstraintKind.ORIENTATION or not isinstance(c, OrientationConstraint):
            continue
        if c.hard:
            continue
        p = placement_map.get(c.room_id)
        if p is None:
            violations.append(
                Violation(
                    constraint_id=c.id,
                    room_ids=[c.room_id],
                    message=f"朝向偏好未满足：房间缺失（期望世界 {c.preferred_orientation}）",
                    hard=False,
                    source=c.source.value,
                )
            )
            continue
        model_edges = exterior_model_edges(from_placement(p.rect), buildable)
        faces = {
            coords.world_orientation_for_edge(e).value for e in model_edges
        }
        preferred = c.preferred_orientation.lower()
        if preferred not in faces:
            model_for_pref = sorted(coords.model_edges_facing(preferred))
            violations.append(
                Violation(
                    constraint_id=c.id,
                    room_ids=[c.room_id],
                    message=(
                        f"朝向偏好未满足：期望世界 {preferred} "
                        f"(north_angle={coords.north_angle:.0f}° → model 边 {model_for_pref or ['无']})，"
                        f"实际 model={sorted(model_edges) or ['无']} "
                        f"→ 世界={sorted(faces) or ['无']}"
                    ),
                    hard=False,
                    source=c.source.value,
                )
            )
    return violations


def orientation_score(metrics: dict[str, float | int]) -> float:
    sat = float(metrics.get("orientation_satisfaction", 1.0))
    return max(0.0, min(100.0, sat * 100.0))


# 再导出，便于类型提示
__all__ = [
    "CardinalOrientation",
    "EDGE_TOLERANCE",
    "compute_orientation_metrics",
    "exterior_model_edges",
    "exterior_orientations",
    "exterior_world_orientations",
    "orientation_score",
    "orientation_soft_violations",
]

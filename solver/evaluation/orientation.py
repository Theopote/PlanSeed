"""朝向约束评价 — OrientationConstraint 闭环。"""

from __future__ import annotations

from packages.schema.constraints import ConstraintKind, OrientationConstraint
from packages.schema.layout import LayoutCandidate, Violation
from packages.schema.program import DesignProgram
from solver.geometry.rect import Rect, exterior_edges, from_placement

EDGE_TOLERANCE = 0.05  # m：贴外墙判定


def exterior_orientations(
    room_rect: Rect,
    buildable: Rect,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> set[str]:
    """
    房间贴靠 buildable 外缘的朝向集合。

    坐标系：y=0 为北，y 增大向南；x=0 为西，x 增大向东。
    """
    return set(exterior_edges(room_rect, buildable, tolerance=tolerance))


def compute_orientation_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float | int]:
    """
    评价 OrientationConstraint 满足度。

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
        }

    buildable = Rect(
        x=program.buildable.x,
        y=program.buildable.y,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )
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
        faces = exterior_orientations(from_placement(p.rect), buildable)
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
    }


def orientation_soft_violations(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[Violation]:
    """未满足的 soft OrientationConstraint → soft violations（可解释）。"""
    buildable = Rect(
        x=program.buildable.x,
        y=program.buildable.y,
        width=program.buildable.width,
        depth=program.buildable.depth,
    )
    placement_map = {
        p.room_id: p for fl in candidate.floors for p in fl.placements
    }
    violations: list[Violation] = []

    for c in program.constraints:
        if c.kind != ConstraintKind.ORIENTATION or not isinstance(c, OrientationConstraint):
            continue
        if c.hard:
            continue  # hard 由 ConstraintChecker 处理
        p = placement_map.get(c.room_id)
        if p is None:
            violations.append(
                Violation(
                    constraint_id=c.id,
                    room_ids=[c.room_id],
                    message=f"朝向偏好未满足：房间缺失（期望 {c.preferred_orientation}）",
                    hard=False,
                    source=c.source.value,
                )
            )
            continue
        faces = exterior_orientations(from_placement(p.rect), buildable)
        if c.preferred_orientation.lower() not in faces:
            violations.append(
                Violation(
                    constraint_id=c.id,
                    room_ids=[c.room_id],
                    message=(
                        f"朝向偏好未满足：期望贴 {c.preferred_orientation} 外墙，"
                        f"实际外墙朝向={sorted(faces) or ['无']}"
                    ),
                    hard=False,
                    source=c.source.value,
                )
            )
    return violations


def orientation_score(metrics: dict[str, float | int]) -> float:
    sat = float(metrics.get("orientation_satisfaction", 1.0))
    return max(0.0, min(100.0, sat * 100.0))

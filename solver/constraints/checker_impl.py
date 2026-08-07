"""Hard / soft 约束校验。"""

from __future__ import annotations

from packages.schema.constraints import (
    AdjacencyConstraint,
    AlignmentConstraint,
    AreaConstraint,
    ConstraintKind,
    WidthConstraint,
)
from packages.schema.layout import CandidateValidation, LayoutCandidate, Violation
from packages.schema.program import DesignProgram
from solver.constraints.checker import ConstraintChecker
from solver.geometry.rect import Rect, contains, from_placement, intersects, shared_edge_length

OVERLAP_TOLERANCE = 1e-4
MIN_ADJACENCY_WALL = 1.2


class DefaultConstraintChecker:
    """Phase 1 约束校验器。"""

    def check(self, program: DesignProgram, candidate: LayoutCandidate) -> CandidateValidation:
        hard: list[Violation] = []
        soft: list[Violation] = []
        warnings: list[str] = []

        buildable = Rect(
            x=program.buildable.x,
            y=program.buildable.y,
            width=program.buildable.width,
            depth=program.buildable.depth,
        )

        hard.extend(self._check_overlaps(candidate))
        hard.extend(self._check_boundary(candidate, buildable))
        hard.extend(self._check_area_and_width(program, candidate))
        hard.extend(self._check_stair_alignment(candidate))

        for constraint in program.constraints:
            if constraint.kind == ConstraintKind.ADJACENCY and not constraint.hard:
                v = self._check_adjacency_soft(constraint, candidate)
                if v:
                    soft.append(v)
            elif constraint.kind == ConstraintKind.ALIGNMENT:
                v = self._check_alignment(constraint, candidate)
                if v:
                    (hard if constraint.hard else soft).append(v)

        # 湿区对齐：默认 soft
        wet_v = self._check_wet_alignment(candidate)
        if wet_v:
            soft.append(wet_v)

        return CandidateValidation(
            valid=len(hard) == 0,
            hard_violations=hard,
            soft_violations=soft,
            warnings=warnings,
        )

    def _placements_by_floor(self, candidate: LayoutCandidate) -> dict[str, list]:
        return {fl.floor_id: fl.placements for fl in candidate.floors}

    def _check_overlaps(self, candidate: LayoutCandidate) -> list[Violation]:
        violations: list[Violation] = []
        for floor in candidate.floors:
            placements = floor.placements
            for i, a in enumerate(placements):
                ra = from_placement(a.rect)
                for b in placements[i + 1 :]:
                    rb = from_placement(b.rect)
                    inter = intersects(ra, rb)
                    if not inter:
                        continue
                    # 允许贴边，不允许面积重叠
                    overlap_w = min(ra.right, rb.right) - max(ra.left, rb.left)
                    overlap_h = min(ra.bottom, rb.bottom) - max(ra.top, rb.top)
                    if overlap_w > OVERLAP_TOLERANCE and overlap_h > OVERLAP_TOLERANCE:
                        violations.append(
                            Violation(
                                constraint_id="geometry.overlap",
                                room_ids=[a.room_id, b.room_id],
                                message=f"房间重叠：{a.room_id} 与 {b.room_id}",
                                hard=True,
                                source="system",
                            )
                        )
        return violations

    def _check_boundary(self, candidate: LayoutCandidate, buildable: Rect) -> list[Violation]:
        violations: list[Violation] = []
        for floor in candidate.floors:
            for p in floor.placements:
                r = from_placement(p.rect)
                if not contains(buildable, r):
                    violations.append(
                        Violation(
                            constraint_id="geometry.boundary",
                            room_ids=[p.room_id],
                            message=f"房间 {p.room_id} 超出可建范围",
                            hard=True,
                            source="system",
                        )
                    )
        return violations

    def _check_area_and_width(
        self, program: DesignProgram, candidate: LayoutCandidate
    ) -> list[Violation]:
        violations: list[Violation] = []
        placement_map = {
            p.room_id: p for fl in candidate.floors for p in fl.placements
        }

        for constraint in program.constraints:
            if constraint.kind == ConstraintKind.AREA and isinstance(constraint, AreaConstraint):
                p = placement_map.get(constraint.room_id)
                if p is None:
                    continue
                area = p.rect.area
                if constraint.min_area is not None and area < constraint.min_area - 1e-6:
                    violations.append(
                        Violation(
                            constraint_id=constraint.id,
                            room_ids=[constraint.room_id],
                            message=f"面积不足：{area:.2f} < {constraint.min_area:.2f}",
                            measured_value=area,
                            required_value=constraint.min_area,
                            hard=constraint.hard,
                            source=constraint.source.value,
                        )
                    )
            elif constraint.kind == ConstraintKind.WIDTH and isinstance(constraint, WidthConstraint):
                p = placement_map.get(constraint.room_id)
                if p is None:
                    continue
                min_dim = min(p.rect.width, p.rect.depth)
                if min_dim < constraint.min_width - 1e-6:
                    violations.append(
                        Violation(
                            constraint_id=constraint.id,
                            room_ids=[constraint.room_id],
                            message=f"净宽不足：{min_dim:.2f} < {constraint.min_width:.2f}",
                            measured_value=min_dim,
                            required_value=constraint.min_width,
                            hard=constraint.hard,
                            source=constraint.source.value,
                        )
                    )
        return [v for v in violations if v.hard]

    def _check_stair_alignment(self, candidate: LayoutCandidate) -> list[Violation]:
        if len(candidate.floors) < 2:
            return []
        refs = candidate.floors[0]
        if refs.stair_x0 is None or refs.stair_x1 is None:
            return []
        violations: list[Violation] = []
        for fl in candidate.floors[1:]:
            if fl.stair_x0 is None or fl.stair_x1 is None:
                continue
            if abs(fl.stair_x0 - refs.stair_x0) > 0.01 or abs(fl.stair_x1 - refs.stair_x1) > 0.01:
                violations.append(
                    Violation(
                        constraint_id="vertical.stair_alignment",
                        room_ids=[],
                        message="楼梯 x 区间跨层未对齐",
                        measured_value=fl.stair_x1 - fl.stair_x0,
                        required_value=refs.stair_x1 - refs.stair_x0,
                        hard=True,
                        source="system",
                    )
                )
        return violations

    def _check_wet_alignment(self, candidate: LayoutCandidate) -> Violation | None:
        if len(candidate.floors) < 2:
            return None
        ref = candidate.floors[0]
        if ref.wet_zone_x0 is None or ref.wet_zone_x1 is None:
            return None
        for fl in candidate.floors[1:]:
            if fl.wet_zone_x0 is None or fl.wet_zone_x1 is None:
                continue
            if abs(fl.wet_zone_x0 - ref.wet_zone_x0) > 0.01 or abs(fl.wet_zone_x1 - ref.wet_zone_x1) > 0.01:
                return Violation(
                    constraint_id="vertical.wet_zone_alignment",
                    room_ids=[],
                    message="湿区 x 区间跨层未对齐",
                    hard=False,
                    source="system",
                )
        return None

    def _check_adjacency_soft(
        self, constraint: AdjacencyConstraint, candidate: LayoutCandidate
    ) -> Violation | None:
        pa = pb = None
        for fl in candidate.floors:
            for p in fl.placements:
                if p.room_id == constraint.room_a_id:
                    pa = p
                if p.room_id == constraint.room_b_id:
                    pb = p
        if pa is None or pb is None or pa.floor_id != pb.floor_id:
            return Violation(
                constraint_id=constraint.id,
                room_ids=[constraint.room_a_id, constraint.room_b_id],
                message="偏好邻接未满足（未同层或未接触）",
                hard=False,
                source=constraint.source.value,
            )
        shared = shared_edge_length(from_placement(pa.rect), from_placement(pb.rect))
        if shared < MIN_ADJACENCY_WALL:
            return Violation(
                constraint_id=constraint.id,
                room_ids=[constraint.room_a_id, constraint.room_b_id],
                message=f"邻接共享墙不足：{shared:.2f}m < {MIN_ADJACENCY_WALL}m",
                measured_value=shared,
                required_value=MIN_ADJACENCY_WALL,
                hard=False,
                source=constraint.source.value,
            )
        return None

    def _check_alignment(
        self, constraint: AlignmentConstraint, candidate: LayoutCandidate
    ) -> Violation | None:
        if constraint.alignment_group == "wet_zone":
            return self._check_wet_alignment(candidate)
        if constraint.alignment_group == "stair":
            hard = self._check_stair_alignment(candidate)
            return hard[0] if hard else None
        return None


# 保留 Protocol 别名
ConstraintCheckerImpl = DefaultConstraintChecker

"""Hard / soft 约束校验 — 子检查统一返回 ConstraintEvaluationResult。"""

from __future__ import annotations

from packages.schema.constraints import (
    AdjacencyConstraint,
    AlignmentConstraint,
    AreaConstraint,
    ConstraintKind,
    OrientationConstraint,
    WidthConstraint,
)
from packages.schema.layout import CandidateValidation, LayoutCandidate, Violation
from packages.schema.program import DesignProgram
from solver.constraints.checker import ConstraintEvaluationResult
from solver.evaluation.orientation import exterior_orientations
from solver.geometry.rect import Rect, contains, from_placement, intersects, shared_edge_length

OVERLAP_TOLERANCE = 1e-4
MIN_ADJACENCY_WALL = 1.2


class DefaultConstraintChecker:
    """Phase 1.5 约束校验器。"""

    def check(self, program: DesignProgram, candidate: LayoutCandidate) -> CandidateValidation:
        result = ConstraintEvaluationResult.empty()

        buildable = Rect(
            x=program.buildable.x,
            y=program.buildable.y,
            width=program.buildable.width,
            depth=program.buildable.depth,
        )

        result.extend(self._check_overlaps(candidate))
        result.extend(self._check_boundary(candidate, buildable))
        result.extend(self._check_area_and_width(program, candidate))
        result.extend(self._check_stair_alignment(candidate))

        for constraint in program.constraints:
            if constraint.kind == ConstraintKind.ADJACENCY and isinstance(
                constraint, AdjacencyConstraint
            ):
                result.extend(self._check_adjacency(constraint, candidate))
            elif constraint.kind == ConstraintKind.ORIENTATION and isinstance(
                constraint, OrientationConstraint
            ):
                # hard orientation → validation；soft 由 Evaluator 评分
                if constraint.hard:
                    result.extend(self._check_orientation_hard(constraint, candidate, buildable))
            elif constraint.kind == ConstraintKind.ALIGNMENT and isinstance(
                constraint, AlignmentConstraint
            ):
                result.extend(self._check_alignment(constraint, candidate))

        has_explicit_wet = any(
            isinstance(c, AlignmentConstraint) and c.alignment_group == "wet_zone"
            for c in program.constraints
        )
        if not has_explicit_wet:
            result.extend(self._check_wet_alignment(candidate))

        return result.to_candidate_validation()

    def _check_overlaps(self, candidate: LayoutCandidate) -> ConstraintEvaluationResult:
        violations: list[Violation] = []
        for floor in candidate.floors:
            placements = floor.placements
            for i, a in enumerate(placements):
                ra = from_placement(a.rect)
                for b in placements[i + 1 :]:
                    rb = from_placement(b.rect)
                    if not intersects(ra, rb):
                        continue
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
        return ConstraintEvaluationResult.from_violations(violations)

    def _check_boundary(
        self, candidate: LayoutCandidate, buildable: Rect
    ) -> ConstraintEvaluationResult:
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
        return ConstraintEvaluationResult.from_violations(violations)

    def _check_area_and_width(
        self, program: DesignProgram, candidate: LayoutCandidate
    ) -> ConstraintEvaluationResult:
        """
        面积 / 宽度约束。

        hard 与 soft 全部保留，由 from_violations 分流；禁止在此过滤 soft。
        """
        violations: list[Violation] = []
        placement_map = {p.room_id: p for fl in candidate.floors for p in fl.placements}

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
                if constraint.max_area is not None and area > constraint.max_area + 1e-6:
                    violations.append(
                        Violation(
                            constraint_id=constraint.id,
                            room_ids=[constraint.room_id],
                            message=f"面积过大：{area:.2f} > {constraint.max_area:.2f}",
                            measured_value=area,
                            required_value=constraint.max_area,
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

        return ConstraintEvaluationResult.from_violations(violations)

    def _check_stair_alignment(self, candidate: LayoutCandidate) -> ConstraintEvaluationResult:
        if len(candidate.floors) < 2:
            return ConstraintEvaluationResult.empty()
        refs = candidate.floors[0]
        if refs.stair_x0 is None or refs.stair_x1 is None:
            return ConstraintEvaluationResult.empty()
        if refs.stair_y0 is None or refs.stair_y1 is None:
            return ConstraintEvaluationResult.empty()

        violations: list[Violation] = []
        for fl in candidate.floors[1:]:
            if None in (fl.stair_x0, fl.stair_x1, fl.stair_y0, fl.stair_y1):
                continue
            aligned = (
                abs(fl.stair_x0 - refs.stair_x0) <= 0.01
                and abs(fl.stair_x1 - refs.stair_x1) <= 0.01
                and abs(fl.stair_y0 - refs.stair_y0) <= 0.01
                and abs(fl.stair_y1 - refs.stair_y1) <= 0.01
            )
            if not aligned:
                violations.append(
                    Violation(
                        constraint_id="vertical.stair_alignment",
                        room_ids=[],
                        message="楼梯核跨层未对齐",
                        measured_value=(fl.stair_x1 - fl.stair_x0) if fl.stair_x1 and fl.stair_x0 else None,
                        required_value=(refs.stair_x1 - refs.stair_x0) if refs.stair_x1 and refs.stair_x0 else None,
                        hard=True,
                        source="system",
                    )
                )
        return ConstraintEvaluationResult.from_violations(violations)

    def _check_wet_alignment(self, candidate: LayoutCandidate) -> ConstraintEvaluationResult:
        if len(candidate.floors) < 2:
            return ConstraintEvaluationResult.empty()
        ref = candidate.floors[0]
        if ref.wet_zone_x0 is None or ref.wet_zone_x1 is None:
            return ConstraintEvaluationResult.empty()
        for fl in candidate.floors[1:]:
            if fl.wet_zone_x0 is None or fl.wet_zone_x1 is None:
                continue
            if abs(fl.wet_zone_x0 - ref.wet_zone_x0) > 0.01 or abs(fl.wet_zone_x1 - ref.wet_zone_x1) > 0.01:
                return ConstraintEvaluationResult.from_violations(
                    [
                        Violation(
                            constraint_id="vertical.wet_zone_alignment",
                            room_ids=[],
                            message="湿区 x 区间跨层未对齐",
                            hard=False,
                            source="system",
                        )
                    ]
                )
        return ConstraintEvaluationResult.empty()

    def _check_adjacency(
        self, constraint: AdjacencyConstraint, candidate: LayoutCandidate
    ) -> ConstraintEvaluationResult:
        """Hard / soft 邻接统一检查：同层且共享墙 ≥ MIN_ADJACENCY_WALL。"""
        pa = pb = None
        for fl in candidate.floors:
            for p in fl.placements:
                if p.room_id == constraint.room_a_id:
                    pa = p
                if p.room_id == constraint.room_b_id:
                    pb = p

        label = "强制邻接" if constraint.hard else "偏好邻接"

        if pa is None or pb is None:
            return ConstraintEvaluationResult.from_optional(
                Violation(
                    constraint_id=constraint.id,
                    room_ids=[constraint.room_a_id, constraint.room_b_id],
                    message=f"{label}未满足：房间缺失",
                    hard=constraint.hard,
                    source=constraint.source.value,
                )
            )
        if pa.floor_id != pb.floor_id:
            return ConstraintEvaluationResult.from_optional(
                Violation(
                    constraint_id=constraint.id,
                    room_ids=[constraint.room_a_id, constraint.room_b_id],
                    message=f"{label}未满足：不在同层（{pa.floor_id} vs {pb.floor_id}）",
                    hard=constraint.hard,
                    source=constraint.source.value,
                )
            )

        shared = shared_edge_length(from_placement(pa.rect), from_placement(pb.rect))
        if shared < MIN_ADJACENCY_WALL:
            return ConstraintEvaluationResult.from_optional(
                Violation(
                    constraint_id=constraint.id,
                    room_ids=[constraint.room_a_id, constraint.room_b_id],
                    message=f"{label}共享墙不足：{shared:.2f}m < {MIN_ADJACENCY_WALL}m",
                    measured_value=shared,
                    required_value=MIN_ADJACENCY_WALL,
                    hard=constraint.hard,
                    source=constraint.source.value,
                )
            )
        return ConstraintEvaluationResult.empty()

    def _check_alignment(
        self, constraint: AlignmentConstraint, candidate: LayoutCandidate
    ) -> ConstraintEvaluationResult:
        if constraint.alignment_group == "wet_zone":
            result = self._check_wet_alignment(candidate)
            # 尊重 constraint.hard：默认湿区检查产出 soft，若声明为 hard 则提升
            if constraint.hard and result.soft_violations:
                promoted = [
                    v.model_copy(update={"hard": True, "constraint_id": constraint.id})
                    for v in result.soft_violations
                ]
                return ConstraintEvaluationResult(hard_violations=promoted)
            if result.soft_violations:
                return ConstraintEvaluationResult(
                    soft_violations=[
                        v.model_copy(update={"constraint_id": constraint.id})
                        for v in result.soft_violations
                    ]
                )
            return result
        if constraint.alignment_group == "stair":
            result = self._check_stair_alignment(candidate)
            if not constraint.hard and result.hard_violations:
                demoted = [
                    v.model_copy(update={"hard": False, "constraint_id": constraint.id})
                    for v in result.hard_violations
                ]
                return ConstraintEvaluationResult(soft_violations=demoted)
            return result
        return ConstraintEvaluationResult.empty()

    def _check_orientation_hard(
        self,
        constraint: OrientationConstraint,
        candidate: LayoutCandidate,
        buildable: Rect,
    ) -> ConstraintEvaluationResult:
        placement = None
        for fl in candidate.floors:
            for p in fl.placements:
                if p.room_id == constraint.room_id:
                    placement = p
                    break
        if placement is None:
            return ConstraintEvaluationResult.from_optional(
                Violation(
                    constraint_id=constraint.id,
                    room_ids=[constraint.room_id],
                    message=f"强制朝向未满足：房间缺失（期望 {constraint.preferred_orientation}）",
                    hard=True,
                    source=constraint.source.value,
                )
            )
        faces = exterior_orientations(from_placement(placement.rect), buildable)
        if constraint.preferred_orientation.lower() not in faces:
            return ConstraintEvaluationResult.from_optional(
                Violation(
                    constraint_id=constraint.id,
                    room_ids=[constraint.room_id],
                    message=(
                        f"强制朝向未满足：期望贴 {constraint.preferred_orientation} 外墙，"
                        f"实际={sorted(faces) or ['无']}"
                    ),
                    hard=True,
                    source=constraint.source.value,
                )
            )
        return ConstraintEvaluationResult.empty()


ConstraintCheckerImpl = DefaultConstraintChecker

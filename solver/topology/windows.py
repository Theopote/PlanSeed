"""
外窗标注 — daylight_required 房间与建筑外轮廓的几何连接。

落在真实 ``ExteriorWallSegment`` 中段；无外墙时产出 DesignFinding。
"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate, RoomPlacement, WindowOpening
from packages.schema.program import DesignProgram
from packages.schema.room import RoomSpec
from packages.schema.scoring import DesignFinding, EvaluationAxis, FindingSeverity
from solver.evaluation.findings import finding
from solver.evaluation.orientation import EDGE_TOLERANCE
from solver.geometry.exterior import ExteriorWallSegment, pick_longest_exterior_segment
from solver.geometry.rect import from_placement

MIN_WINDOW_WIDTH = 0.9
MAX_WINDOW_WIDTH = 3.0
_WINDOW_FRAC_MIN = 0.30
_WINDOW_FRAC_MAX = 0.50


def _window_width_for_edge(edge_length: float, room_id: str) -> float:
    """沿外墙长度 30%～50%，并夹在 [0.9, 3.0] m；不超过墙段总长。"""
    if edge_length <= 1e-9:
        return MIN_WINDOW_WIDTH
    span = _WINDOW_FRAC_MAX - _WINDOW_FRAC_MIN
    h = sum(ord(c) for c in room_id) % 101
    frac = _WINDOW_FRAC_MIN + span * (h / 100.0)
    raw = edge_length * frac
    width = max(MIN_WINDOW_WIDTH, min(MAX_WINDOW_WIDTH, raw))
    return min(width, edge_length)


def _pick_exterior_segment(
    room_rect,
    program: DesignProgram,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> ExteriorWallSegment | None:
    """取可贴窗的最长真实外墙段。"""
    return pick_longest_exterior_segment(
        room_rect, program, tolerance=tolerance, min_length=MIN_WINDOW_WIDTH
    )


def _find_placement(
    candidate: LayoutCandidate,
    room_id: str,
    floor_id: str | None,
) -> tuple[RoomPlacement, str] | None:
    for fl in candidate.floors:
        if floor_id is not None and fl.floor_id != floor_id:
            continue
        for p in fl.placements:
            if p.room_id == room_id:
                return p, fl.floor_id
    return None


def _no_exterior_wall_finding(room: RoomSpec) -> DesignFinding:
    return finding(
        id=f"environment.daylight_no_exterior_wall.{room.id}",
        category=EvaluationAxis.ENVIRONMENT.value,
        severity=FindingSeverity.WARNING,
        title="采光房间无外墙",
        message=(
            f"「{room.name}」要求自然采光，但当前放置四周均未贴靠建筑外轮廓，"
            "无法布置外窗。"
        ),
        room_ids=[room.id],
        metric="daylight_exterior_wall",
        measured_value=0.0,
        recommended_action="将房间调整至外墙边，或考虑天井/采光井等竖向采光措施。",
    )


def place_window_openings(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[DesignFinding]:
    """
    为 daylight_required 房间生成 WindowOpening；无外墙时写入 DesignFinding。

    结果写入各层 FloorLayout.window_openings（覆盖旧值）。
    """
    findings: list[DesignFinding] = []

    for fl in candidate.floors:
        fl.window_openings = []

    seq = 0
    for room in program.rooms:
        if not room.daylight_required:
            continue
        located = _find_placement(candidate, room.id, room.floor_id)
        if located is None:
            continue
        placement, floor_id = located
        room_rect = from_placement(placement.rect)
        seg = _pick_exterior_segment(room_rect, program)
        if seg is None:
            findings.append(_no_exterior_wall_finding(room))
            continue

        width = _window_width_for_edge(seg.length, room.id)
        seq += 1
        opening = WindowOpening(
            id=f"win-{floor_id}-{room.id}-{seq}",
            room_id=room.id,
            floor_id=floor_id,
            x=seg.mid_x,
            y=seg.mid_y,
            width=width,
            axis=seg.axis,  # type: ignore[arg-type]
        )
        for fl in candidate.floors:
            if fl.floor_id == floor_id:
                fl.window_openings.append(opening)
                break

    return findings


def collect_daylight_findings(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> list[DesignFinding]:
    """评价阶段并入：daylight_required 且无贴外墙的房间。"""
    findings: list[DesignFinding] = []
    for room in program.rooms:
        if not room.daylight_required:
            continue
        located = _find_placement(candidate, room.id, room.floor_id)
        if located is None:
            continue
        placement, _ = located
        if _pick_exterior_segment(from_placement(placement.rect), program) is None:
            findings.append(_no_exterior_wall_finding(room))
    return findings

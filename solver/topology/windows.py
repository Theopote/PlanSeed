"""
外窗标注 — daylight_required 房间与建筑外轮廓的几何连接。

复用 orientation / exterior_edges 判定贴外墙；无外墙时产出 DesignFinding。
"""

from __future__ import annotations

from typing import Literal

from packages.schema.layout import LayoutCandidate, RoomPlacement, WindowOpening
from packages.schema.program import DesignProgram
from packages.schema.room import RoomSpec
from packages.schema.scoring import DesignFinding, EvaluationAxis, FindingSeverity
from solver.evaluation.findings import finding
from solver.evaluation.orientation import EDGE_TOLERANCE
from solver.geometry.rect import Rect, exterior_edges, from_placement, program_local_buildable

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


def _edge_opening_geometry(
    room: Rect,
    edge: str,
    edge_length: float,
) -> tuple[float, float, Literal["x", "y"]]:
    """外墙段中点与墙走向。"""
    if edge == "north":
        return room.x + room.width / 2, room.top, "x"
    if edge == "south":
        return room.x + room.width / 2, room.bottom, "x"
    if edge == "west":
        return room.left, room.y + room.depth / 2, "y"
    return room.right, room.y + room.depth / 2, "y"


def _pick_exterior_edge(
    room_rect: Rect,
    buildable: Rect,
    *,
    tolerance: float = EDGE_TOLERANCE,
) -> tuple[str, float] | None:
    """取贴外墙中最长的一段；无则 None。"""
    edges = exterior_edges(room_rect, buildable, tolerance=tolerance)
    if not edges:
        return None
    return max(edges.items(), key=lambda kv: kv[1])


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
    buildable = program_local_buildable(program)
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
        picked = _pick_exterior_edge(room_rect, buildable)
        if picked is None:
            findings.append(_no_exterior_wall_finding(room))
            continue

        edge_name, edge_len = picked
        mid_x, mid_y, axis = _edge_opening_geometry(room_rect, edge_name, edge_len)
        width = _window_width_for_edge(edge_len, room.id)
        seq += 1
        opening = WindowOpening(
            id=f"win-{floor_id}-{room.id}-{seq}",
            room_id=room.id,
            floor_id=floor_id,
            x=mid_x,
            y=mid_y,
            width=width,
            axis=axis,
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
    buildable = program_local_buildable(program)
    findings: list[DesignFinding] = []
    for room in program.rooms:
        if not room.daylight_required:
            continue
        located = _find_placement(candidate, room.id, room.floor_id)
        if located is None:
            continue
        placement, _ = located
        if _pick_exterior_edge(from_placement(placement.rect), buildable) is None:
            findings.append(_no_exterior_wall_finding(room))
    return findings

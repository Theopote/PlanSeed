"""Circulation metrics — Phase 2.3 foundation（RealizedAccessGraph）。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from solver.topology.access import (
    ENTRY_NODE_ID,
    access_depths,
    build_realized_access_graph,
    occupied_room_ids,
    reachable_nodes,
)
from solver.topology.derive_access import ensure_access_graph


def _circulation_compatible(program: DesignProgram, room_id: str) -> bool:
    room = program.room_by_id(room_id)
    if room is None:
        return room_id.startswith("stair-") or room_id == ENTRY_NODE_ID
    if room.category == RoomCategory.CIRCULATION:
        return True
    if room.category == RoomCategory.PUBLIC:
        return True  # 厅作为过渡可接受；卧室穿堂另计
    return False


def compute_circulation_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float]:
    """
    reachable_ratio / access depth / dead_end / through_room 初版。
    """
    ensure_access_graph(program)
    graph = build_realized_access_graph(program, candidate)
    occupied = occupied_room_ids(program)
    if not occupied:
        return {
            "reachable_ratio": 1.0,
            "average_access_depth": 0.0,
            "max_access_depth": 0.0,
            "dead_end_count": 0.0,
            "through_room_count": 0.0,
            "layout_stability_score": 100.0,
        }

    reached = reachable_nodes(graph, start=ENTRY_NODE_ID) & occupied
    depths = access_depths(graph, start=ENTRY_NODE_ID)
    occ_depths = [depths[r] for r in occupied if r in depths]
    avg_d = sum(occ_depths) / len(occ_depths) if occ_depths else 0.0
    max_d = float(max(occ_depths)) if occ_depths else 0.0

    # degree in realized graph
    deg: dict[str, int] = {r: 0 for r in occupied}
    for c in graph.connections:
        if c.a in deg:
            deg[c.a] += 1
        if c.b in deg:
            deg[c.b] += 1
    dead = sum(1 for r, d in deg.items() if r in reached and d <= 1)

    # through-room：非交通兼容节点，若去掉后使其他 occupied 不可达
    through = 0
    for mid in list(reached):
        if _circulation_compatible(program, mid):
            continue
        # 粗略：深度大于 1 且度>=2 的 private/wet 计为潜在穿堂
        if deg.get(mid, 0) >= 2 and depths.get(mid, 0) >= 2:
            cat = None
            room = program.room_by_id(mid)
            if room is not None:
                cat = room.category
            if cat in (RoomCategory.PRIVATE, RoomCategory.WET, RoomCategory.SERVICE):
                through += 1

    stability = float(candidate.metrics.get("layout_stability", 1.0))
    if "layout_stability" not in candidate.metrics:
        repairs = float(candidate.metrics.get("connection_repairs", 0) or 0)
        stability = max(0.0, 1.0 - 0.08 * repairs)

    return {
        "reachable_ratio": round(len(reached) / len(occupied), 4),
        "average_access_depth": round(avg_d, 4),
        "max_access_depth": max_d,
        "dead_end_count": float(dead),
        "through_room_count": float(through),
        "layout_stability_score": round(stability * 100.0, 2),
    }


def circulation_architecture_score(metrics: dict[str, float]) -> float:
    """Phase 3：路径质量（不含 layout_stability，后者单独计分）。"""
    reachable = float(metrics.get("reachable_ratio", 1.0))
    through = float(metrics.get("through_room_count", 0.0))
    dead = float(metrics.get("dead_end_count", 0.0))
    avg_d = float(metrics.get("average_access_depth", 0.0))

    depth_pen = 0.0
    if avg_d > 0:
        if avg_d < 1.5:
            depth_pen = 0.05
        elif avg_d > 5.0:
            depth_pen = min(0.25, (avg_d - 5.0) * 0.05)

    score = (
        100.0 * reachable * 0.70
        + 100.0 * (1.0 - depth_pen) * 0.30
        - through * 6.0
        - dead * 2.0
    )
    return max(0.0, min(100.0, score))

"""通行连接软评价 — AccessGraph 偏好边是否具备共边。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.topology import SpaceConnectionType
from solver.geometry.rect import from_placement, shared_edge_length
from solver.topology.access import MIN_ACCESS_WALL
from solver.topology.derive_access import ensure_access_graph
from solver.topology.doors import find_placements, shared_boundary_between

_OPENING = frozenset(
    {
        SpaceConnectionType.OPEN,
        SpaceConnectionType.DOOR,
        SpaceConnectionType.PASSAGE,
    }
)


def compute_access_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float]:
    """
    access_pref_satisfaction：偏好/必连开口边中已共边的比例。
    access_required_edge_count / access_pref_edge_count：计数。
    """
    graph = ensure_access_graph(program)
    opening = [
        c
        for c in graph.connections
        if c.type in _OPENING and c.a != c.b
        and not str(c.a).startswith("exterior")
        and not str(c.b).startswith("exterior")
    ]
    if not opening:
        return {
            "access_pref_satisfaction": 1.0,
            "access_pref_edge_count": 0.0,
            "access_required_edge_count": 0.0,
            "access_required_satisfaction": 1.0,
        }

    def satisfied(conn) -> bool:
        pas = find_placements(candidate, conn.a)
        pbs = find_placements(candidate, conn.b)
        for pa in pas:
            for pb in pbs:
                if shared_boundary_between(pa, pb, min_length=MIN_ACCESS_WALL):
                    return True
                # 略低于硬门槛的共边仍计 soft 部分命中
                if pas and pbs and pa.floor_id == pb.floor_id:
                    if (
                        shared_edge_length(
                            from_placement(pa.rect), from_placement(pb.rect)
                        )
                        >= MIN_ACCESS_WALL * 0.5
                    ):
                        return True
        return False

    hits = sum(1 for c in opening if satisfied(c))
    required = [c for c in opening if c.required]
    req_hits = sum(1 for c in required if satisfied(c)) if required else 0

    return {
        "access_pref_satisfaction": round(hits / len(opening), 4),
        "access_pref_edge_count": float(len(opening)),
        "access_required_edge_count": float(len(required)),
        "access_required_satisfaction": (
            round(req_hits / len(required), 4) if required else 1.0
        ),
    }


def access_circulation_score(metrics: dict[str, float]) -> float:
    pref = float(metrics.get("access_pref_satisfaction", 1.0))
    req = float(metrics.get("access_required_satisfaction", 1.0))
    # 必连权重大于软偏好
    return max(0.0, min(100.0, (0.65 * req + 0.35 * pref) * 100.0))

"""PrivacyEvaluator — Phase 3：路径隐私过渡。"""

from __future__ import annotations

from collections import defaultdict, deque

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from solver.topology.access import (
    ENTRY_NODE_ID,
    build_realized_access_graph,
    occupied_room_ids,
)
from solver.topology.derive_access import ensure_access_graph

# 隐私层级（越大越私密）
_PRIVACY_RANK: dict[str, int] = {
    "circulation": 0,
    "public": 1,
    "service": 2,
    "wet": 2,
    "other": 1,
    "private": 3,
}


def _category_of(program: DesignProgram, room_id: str) -> str:
    if room_id == ENTRY_NODE_ID or room_id.startswith("stair-"):
        return "circulation"
    room = program.room_by_id(room_id)
    if room is None:
        return "other"
    return room.category.value


def _bfs_parents(graph) -> dict[str, str | None]:
    adj: dict[str, set[str]] = defaultdict(set)
    for c in graph.connections:
        if c.a == c.b:
            continue
        adj[c.a].add(c.b)
        adj[c.b].add(c.a)
    parent: dict[str, str | None] = {ENTRY_NODE_ID: None}
    q: deque[str] = deque([ENTRY_NODE_ID])
    while q:
        cur = q.popleft()
        for nb in adj.get(cur, ()):
            if nb not in parent:
                parent[nb] = cur
                q.append(nb)
    return parent


def _path_to(parent: dict[str, str | None], target: str) -> list[str]:
    if target not in parent:
        return []
    path = [target]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])  # type: ignore[arg-type]
    path.reverse()
    return path


def _transition_penalty(a_cat: str, b_cat: str) -> float:
    """单步过渡惩罚 ∈ [0, 1]。"""
    if a_cat == b_cat:
        if a_cat == "private":
            return 1.0  # 穿卧室
        if a_cat == "wet":
            return 0.8  # 穿卫生间
        return 0.0
    ra, rb = _PRIVACY_RANK.get(a_cat, 1), _PRIVACY_RANK.get(b_cat, 1)
    # 理想：层级递增或经 circulation
    if a_cat == "circulation" or b_cat == "circulation":
        return 0.0
    if rb >= ra:
        # public→private 直接：轻微
        if a_cat == "public" and b_cat == "private":
            return 0.25
        if a_cat == "public" and b_cat == "wet":
            return 0.15
        return 0.05
    # 回退到更公共：轻微
    if a_cat == "private" and b_cat == "public":
        return 0.35
    if a_cat == "wet" and b_cat == "public":
        return 0.2
    if a_cat == "private" and b_cat == "wet":
        return 0.1  # 套房可接受
    return 0.4


def compute_privacy_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float | int]:
    """
    privacy_transition_score：到各 private 房间路径的过渡质量。
    private_through_count：路径上穿其他 private 的次数。
    """
    ensure_access_graph(program)
    graph = build_realized_access_graph(program, candidate)
    parent = _bfs_parents(graph)
    private_ids = [
        r.id
        for r in program.rooms
        if r.category == RoomCategory.PRIVATE
    ]
    if not private_ids:
        return {
            "privacy_transition_score": 1.0,
            "private_through_count": 0,
            "privacy_path_count": 0,
            "bad_privacy_transition_count": 0,
        }

    penalties: list[float] = []
    through = 0
    bad = 0
    explained = 0
    for pid in private_ids:
        path = _path_to(parent, pid)
        if len(path) < 2:
            penalties.append(1.0)  # 不可达 → 最差
            continue
        explained += 1
        path_pen = 0.0
        cats = [_category_of(program, n) for n in path]
        for i in range(len(cats) - 1):
            p = _transition_penalty(cats[i], cats[i + 1])
            path_pen += p
            if p >= 0.8:
                bad += 1
            # 穿另一间 private（非自身）
            if cats[i] == "private" and path[i] != pid:
                through += 1
        # 归一：路径越长允许略多，但封顶
        norm = min(1.0, path_pen / max(1, len(cats) - 1))
        penalties.append(norm)

    avg_pen = sum(penalties) / len(penalties)
    score = max(0.0, 1.0 - avg_pen)
    return {
        "privacy_transition_score": round(score, 4),
        "private_through_count": through,
        "privacy_path_count": explained,
        "bad_privacy_transition_count": bad,
    }


def privacy_score(metrics: dict[str, float | int]) -> float:
    base = float(metrics.get("privacy_transition_score", 1.0)) * 100.0
    through = int(metrics.get("private_through_count", 0))
    bad = int(metrics.get("bad_privacy_transition_count", 0))
    base -= through * 8.0
    base -= bad * 5.0
    return max(0.0, min(100.0, base))

"""PrivacyEvaluator — Phase 3 分数 + Phase 3.5 findings。"""

from __future__ import annotations

from collections import defaultdict, deque

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from packages.schema.scoring import DesignFinding, FindingSeverity
from solver.evaluation.findings import finding
from solver.topology.access import (
    ENTRY_NODE_ID,
    build_realized_access_graph,
)
from solver.topology.derive_access import ensure_access_graph

_PRIVACY_RANK: dict[str, int] = {
    "circulation": 0,
    "public": 1,
    "service": 2,
    "wet": 2,
    "other": 1,
    "private": 3,
}


def _name(program: DesignProgram, room_id: str) -> str:
    if room_id == ENTRY_NODE_ID:
        return "主入口"
    if room_id.startswith("stair-"):
        return "楼梯"
    room = program.room_by_id(room_id)
    return room.name if room is not None else room_id


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
    if a_cat == b_cat:
        if a_cat == "private":
            return 1.0
        if a_cat == "wet":
            return 0.8
        return 0.0
    ra, rb = _PRIVACY_RANK.get(a_cat, 1), _PRIVACY_RANK.get(b_cat, 1)
    if a_cat == "circulation" or b_cat == "circulation":
        return 0.0
    if rb >= ra:
        if a_cat == "public" and b_cat == "private":
            return 0.25
        if a_cat == "public" and b_cat == "wet":
            return 0.15
        return 0.05
    if a_cat == "private" and b_cat == "public":
        return 0.35
    if a_cat == "wet" and b_cat == "public":
        return 0.2
    if a_cat == "private" and b_cat == "wet":
        return 0.1
    return 0.4


def compute_privacy_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float | int]:
    ensure_access_graph(program)
    graph = build_realized_access_graph(program, candidate)
    parent = _bfs_parents(graph)
    private_ids = [
        r.id for r in program.rooms if r.category == RoomCategory.PRIVATE
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
            penalties.append(1.0)
            continue
        explained += 1
        path_pen = 0.0
        cats = [_category_of(program, n) for n in path]
        for i in range(len(cats) - 1):
            p = _transition_penalty(cats[i], cats[i + 1])
            path_pen += p
            if p >= 0.8:
                bad += 1
            if cats[i] == "private" and path[i] != pid:
                through += 1
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


def privacy_findings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    metrics: dict[str, float | int] | None = None,
) -> list[DesignFinding]:
    """从 realized 路径生成隐私设计发现。"""
    ensure_access_graph(program)
    graph = build_realized_access_graph(program, candidate)
    parent = _bfs_parents(graph)
    private_ids = [
        r.id for r in program.rooms if r.category == RoomCategory.PRIVATE
    ]
    out: list[DesignFinding] = []
    m = metrics or compute_privacy_metrics(program, candidate)

    if not private_ids:
        out.append(
            finding(
                id="privacy.no_private_rooms",
                category="privacy",
                severity=FindingSeverity.INFO,
                title="无私密房间",
                message="程序中无 private 类别房间，跳过隐私路径评价。",
            )
        )
        return out

    good_via_hall = 0
    for pid in private_ids:
        path = _path_to(parent, pid)
        target_name = _name(program, pid)
        if len(path) < 2:
            out.append(
                finding(
                    id=f"privacy.unreachable:{pid}",
                    category="privacy",
                    severity=FindingSeverity.PROBLEM,
                    title=f"{target_name} 不可达",
                    message=f"从主入口无法经 realized 开口到达「{target_name}」。",
                    room_ids=[pid],
                    metric="reachable",
                    measured_value=0.0,
                    recommended_action="检查门洞 / AccessIntent / ConnectionResolver。",
                )
            )
            continue

        cats = [_category_of(program, n) for n in path]
        # 穿其他 private
        through_nodes = [
            path[i]
            for i in range(len(path) - 1)
            if cats[i] == "private" and path[i] != pid
        ]
        if through_nodes:
            mid = through_nodes[0]
            mid_name = _name(program, mid)
            out.append(
                finding(
                    id=f"privacy.private_through_room:{pid}",
                    category="privacy",
                    severity=FindingSeverity.PROBLEM,
                    title=f"访问{target_name}需穿{mid_name}",
                    message=(
                        f"「{target_name}」的主要访问路径需要穿过「{mid_name}」"
                        f"（路径：{' → '.join(_name(program, n) for n in path)}）。"
                    ),
                    room_ids=[pid, mid],
                    metric="private_through_count",
                    measured_value=float(len(through_nodes)),
                    recommended_action="增加公共走廊或调整卧室开门，避免卧室互穿。",
                )
            )

        # 经 circulation 到达 → 优势
        if "circulation" in cats[:-1] and cats[-1] == "private":
            good_via_hall += 1

        # 深度偏大
        depth = len(path) - 1
        if depth >= 4:
            out.append(
                finding(
                    id=f"privacy.deep_access:{pid}",
                    category="privacy",
                    severity=FindingSeverity.WARNING,
                    title=f"{target_name} 访问深度 {depth}",
                    message=(
                        f"到达「{target_name}」需 {depth} 步 realized 连接，"
                        "私密区过深可能影响使用。"
                    ),
                    room_ids=[pid],
                    metric="access_depth",
                    measured_value=float(depth),
                    recommended_action="缩短私密区到公共核的路径，或增加同层走廊。",
                )
            )

    if good_via_hall > 0 and int(m.get("private_through_count", 0)) == 0:
        out.append(
            finding(
                id="privacy.via_circulation",
                category="privacy",
                severity=FindingSeverity.POSITIVE,
                title="私密区经交通空间到达",
                message=(
                    f"{good_via_hall} 间卧室可从主入口经走廊/楼梯等交通空间到达，"
                    "未检测到穿其他卧室。"
                ),
                metric="privacy_transition_score",
                measured_value=float(m.get("privacy_transition_score", 1.0)),
            )
        )
    elif int(m.get("private_through_count", 0)) == 0 and good_via_hall == 0:
        # 直接从 public 进 private 也可接受
        if float(m.get("privacy_transition_score", 0)) >= 0.7:
            out.append(
                finding(
                    id="privacy.acceptable_transition",
                    category="privacy",
                    severity=FindingSeverity.POSITIVE,
                    title="隐私过渡可接受",
                    message="卧室访问路径未穿其他私密房间，过渡层级大体合理。",
                    metric="privacy_transition_score",
                    measured_value=float(m.get("privacy_transition_score", 1.0)),
                )
            )

    return out

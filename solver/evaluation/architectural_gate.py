"""Architectural Quality Gate — 建筑可接受性门槛（≠ 硬约束，≠ 法规审查）。

在七轴评分之外识别严重空间组织问题，决定方案是否有资格进入推荐榜单。

级别：
- blocker：严重问题 → ``architectural_gate_pass=False``，选型优先排除
- warning：设计警告 → 可进榜，但写入 findings
- preference：偏好损失 → 仅记录，不挡榜

文案保持 design heuristic；禁止声称合规 / 消防 / 无障碍通过。
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import StrEnum

from packages.schema.layout import LayoutCandidate, PlacementSource, RoomPlacement
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from packages.schema.scoring import DesignFinding, EvaluationAxis, FindingSeverity
from solver.circulation.stair_identity import is_stair_core_placement
from solver.evaluation.findings import finding
from solver.evaluation.privacy import private_ids_lacking_avoiding_path
from solver.geometry.exterior import has_exterior_wall
from solver.geometry.rect import from_placement
from solver.semantics.roles import (
    is_foyer,
    is_guest_bath,
    is_kitchen,
    is_living,
)
from solver.topology.access import (
    ENTRY_NODE_ID,
    build_realized_access_graph,
    occupied_room_ids,
    reachable_nodes,
)
from solver.topology.derive_access import ensure_access_graph

ARCHITECTURAL_GATE_VERSION = "arch-gate-v1"

# 狭长不可用：长宽比超过此阈值视为警告
_SLIVER_ASPECT = 4.0
_SLIVER_MIN_AREA = 3.0


class GateLevel(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"
    PREFERENCE = "preference"


@dataclass(frozen=True)
class GateIssue:
    code: str
    level: GateLevel
    title: str
    message: str
    room_ids: list[str] = field(default_factory=list)
    recommended_action: str | None = None
    measured_value: float | None = None


@dataclass(frozen=True)
class ArchitecturalGateResult:
    passed: bool
    blockers: list[GateIssue]
    warnings: list[GateIssue]
    preferences: list[GateIssue]
    version: str = ARCHITECTURAL_GATE_VERSION

    @property
    def all_issues(self) -> list[GateIssue]:
        return [*self.blockers, *self.warnings, *self.preferences]


def _name(program: DesignProgram, room_id: str) -> str:
    if room_id == ENTRY_NODE_ID:
        return "主入口"
    if room_id.startswith("stair-"):
        return "楼梯"
    room = program.room_by_id(room_id)
    return room.name if room is not None else room_id


def _adj(graph) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for c in graph.connections:
        if c.a == c.b:
            continue
        out[c.a].add(c.b)
        out[c.b].add(c.a)
    return out


def _bfs_path(
    adj: dict[str, set[str]],
    start: str,
    goal: str,
    *,
    avoid: set[str] | None = None,
) -> list[str]:
    """最短路径；``avoid`` 中的节点不可进入（起终点除外）。"""
    if start == goal:
        return [start]
    blocked = set(avoid or ())
    q: deque[tuple[str, list[str]]] = deque([(start, [start])])
    seen = {start}
    while q:
        cur, path = q.popleft()
        for nb in sorted(adj.get(cur, ())):
            if nb in seen:
                continue
            if nb in blocked and nb != goal:
                continue
            nxt = path + [nb]
            if nb == goal:
                return nxt
            seen.add(nb)
            q.append((nb, nxt))
    return []


def _is_publicish(program: DesignProgram, room_id: str) -> bool:
    if room_id == ENTRY_NODE_ID or room_id.startswith("stair-") or room_id.startswith(
        "circ-"
    ):
        return True
    room = program.room_by_id(room_id)
    if room is None:
        return False
    if room.category in (RoomCategory.PUBLIC, RoomCategory.CIRCULATION):
        return True
    return is_foyer(room) or is_living(room)


def _is_private_room(program: DesignProgram, room_id: str) -> bool:
    room = program.room_by_id(room_id)
    return room is not None and room.category == RoomCategory.PRIVATE


def _acceptable_guest_bath_neighbor(program: DesignProgram, room_id: str) -> bool:
    """客卫可接受的直接邻接：公区 / 交通 / 服务；不可接受：私密卧室、厨房。"""
    if room_id.startswith("stair-") or room_id.startswith("circ-"):
        return True
    if room_id == ENTRY_NODE_ID:
        return True
    room = program.room_by_id(room_id)
    if room is None:
        return False
    if is_kitchen(room):
        return False
    if room.category == RoomCategory.PRIVATE:
        return False
    if room.category in (
        RoomCategory.PUBLIC,
        RoomCategory.CIRCULATION,
        RoomCategory.SERVICE,
        RoomCategory.OTHER,
    ):
        return True
    # wet→wet（公卫旁洗衣等）可接受
    if room.category == RoomCategory.WET and not is_guest_bath(room):
        return True
    return False


def _check_unreachable(
    program: DesignProgram, candidate: LayoutCandidate, graph
) -> list[GateIssue]:
    occupied = occupied_room_ids(program)
    if not occupied:
        return []
    reached = reachable_nodes(graph, start=ENTRY_NODE_ID) & occupied
    missing = occupied - reached
    if not missing:
        return []
    names = "、".join(_name(program, r) for r in sorted(missing)[:5])
    return [
        GateIssue(
            code="unreachable_rooms",
            level=GateLevel.BLOCKER,
            title="存在不可达房间",
            message=f"从主入口无法到达部分房间（含：{names}），方案不具备基本使用动线。",
            room_ids=sorted(missing)[:8],
            recommended_action="补门洞或修复必连共边，避免房间成为交通孤岛。",
            measured_value=float(len(missing)),
        )
    ]


def _check_bedroom_chain(program: DesignProgram, candidate: LayoutCandidate) -> list[GateIssue]:
    lacking = private_ids_lacking_avoiding_path(program, candidate)
    if not lacking:
        return []
    names = "、".join(_name(program, r) for r in sorted(lacking)[:5])
    return [
        GateIssue(
            code="bedroom_chain",
            level=GateLevel.BLOCKER,
            title="卧室互穿才能到达",
            message=(
                f"以下卧室无法在不穿过其它卧室的情况下到达（含：{names}），"
                "独立可达性不足。"
            ),
            room_ids=sorted(lacking)[:8],
            recommended_action="增加公共走廊或调整卧室开门，避免卧室串联。",
            measured_value=float(len(lacking)),
        )
    ]


def _check_guest_bath_access(
    program: DesignProgram, candidate: LayoutCandidate, graph
) -> list[GateIssue]:
    adj = _adj(graph)
    issues: list[GateIssue] = []
    for room in program.rooms:
        if not is_guest_bath(room):
            continue
        neighbors = {n for n in adj.get(room.id, ()) if n != room.id}
        if not neighbors:
            # 不可达已由 unreachable 覆盖；孤立客卫仍记 blocker
            issues.append(
                GateIssue(
                    code="guest_bath_isolated",
                    level=GateLevel.BLOCKER,
                    title=f"「{_name(program, room.id)}」无通行邻接",
                    message=f"「{_name(program, room.id)}」在通行图中无邻接房间，无法作为客卫使用。",
                    room_ids=[room.id],
                    recommended_action="将客卫门开向门厅、走廊或公共区。",
                )
            )
            continue
        if any(_acceptable_guest_bath_neighbor(program, n) for n in neighbors):
            continue
        bad_names = "、".join(_name(program, n) for n in sorted(neighbors)[:4])
        issues.append(
            GateIssue(
                code="guest_bath_via_private",
                level=GateLevel.BLOCKER,
                title=f"「{_name(program, room.id)}」开向不当",
                message=(
                    f"「{_name(program, room.id)}」仅与「{bad_names}」相通，"
                    "需经卧室或厨房等不当空间使用，公私分区错误。"
                ),
                room_ids=[room.id, *sorted(neighbors)[:4]],
                recommended_action="将客卫门改开向门厅、走廊或客厅等公区。",
                measured_value=float(len(neighbors)),
            )
        )
    return issues


def _stair_ids(candidate: LayoutCandidate) -> list[str]:
    ids: list[str] = []
    for fl in candidate.floors:
        for p in fl.placements:
            if is_stair_core_placement(p):
                ids.append(p.room_id)
    return ids


def _check_entry_stair(
    program: DesignProgram, candidate: LayoutCandidate, graph
) -> list[GateIssue]:
    """多层时：入口到楼梯不得只能靠穿越卧室；有门厅时应经过门厅。"""
    if len(candidate.floors) < 2:
        return []
    stairs = _stair_ids(candidate)
    if not stairs:
        return []
    adj = _adj(graph)
    private_ids = {
        n
        for n in adj
        if _is_private_room(program, n)
    }

    # 优先：不穿私密房间的可达路径；否则退回任意最短路径
    best_safe: list[str] = []
    best_any: list[str] = []
    for sid in stairs:
        safe = _bfs_path(adj, ENTRY_NODE_ID, sid, avoid=private_ids)
        if safe and (not best_safe or len(safe) < len(best_safe)):
            best_safe = safe
        any_path = _bfs_path(adj, ENTRY_NODE_ID, sid)
        if any_path and (not best_any or len(any_path) < len(best_any)):
            best_any = any_path

    if not best_any:
        return [
            GateIssue(
                code="stair_unreachable",
                level=GateLevel.BLOCKER,
                title="楼梯不可达",
                message="主入口无法到达楼梯核，跨层交通断裂。",
                room_ids=stairs[:4],
                recommended_action="保证门厅/公区与楼梯贴邻并开通口。",
            )
        ]

    if not best_safe:
        private_on_path = [
            n for n in best_any[1:-1] if _is_private_room(program, n)
        ]
        mid = private_on_path[0] if private_on_path else best_any[1]
        return [
            GateIssue(
                code="entry_stair_via_private",
                level=GateLevel.BLOCKER,
                title="入户到楼梯需穿卧室",
                message=(
                    f"从主入口到楼梯不存在避开私密房间的路径，"
                    f"最短路线穿过「{_name(program, mid)}」"
                    f"（{' → '.join(_name(program, n) for n in best_any)}）。"
                ),
                room_ids=[mid, *stairs[:2]],
                recommended_action="将楼梯贴邻门厅或公共厅，避免经卧室上楼。",
                measured_value=float(len(private_on_path) or 1),
            )
        ]

    best = best_safe
    foyers = [r for r in program.rooms if is_foyer(r)]
    if foyers:
        foyer_ids = {r.id for r in foyers}
        # 有门厅却不在入口→楼梯路径上 → warning（不再用不可达的 public_nodes<=1）
        if not (foyer_ids & set(best)):
            return [
                GateIssue(
                    code="entry_stair_skips_foyer",
                    level=GateLevel.WARNING,
                    title="入户到楼梯未经过门厅",
                    message=(
                        "方案声明了门厅，但主入口到楼梯的路径未经过门厅，"
                        "入口组织可能跳跃。"
                    ),
                    room_ids=sorted(foyer_ids)[:4],
                    recommended_action="让门厅成为入口与楼梯之间的过渡。",
                )
            ]
    return []


def _placement_map(candidate: LayoutCandidate) -> dict[str, RoomPlacement]:
    out: dict[str, RoomPlacement] = {}
    for fl in candidate.floors:
        for p in fl.placements:
            if p.source == PlacementSource.PROGRAM and p.room_id not in out:
                out[p.room_id] = p
    return out


def _check_black_wet(
    program: DesignProgram, candidate: LayoutCandidate
) -> list[GateIssue]:
    """客卫/卫生间无外墙 → 黑卫警告（启发式，非采光规范结论）。"""
    placements = _placement_map(candidate)
    issues: list[GateIssue] = []
    for room in program.rooms:
        if room.category != RoomCategory.WET:
            continue
        if is_kitchen(room):
            continue
        p = placements.get(room.id)
        if p is None:
            continue
        if has_exterior_wall(from_placement(p.rect), program):
            continue
        # daylight_required 的黑房间升为 blocker；普通客卫为 warning
        level = GateLevel.BLOCKER if room.daylight_required else GateLevel.WARNING
        issues.append(
            GateIssue(
                code="black_wet",
                level=level,
                title=f"「{_name(program, room.id)}」无外墙",
                message=(
                    f"「{_name(program, room.id)}」四周未贴靠外轮廓，"
                    "易形成黑卫/暗卫，使用体验差。"
                ),
                room_ids=[room.id],
                recommended_action="将卫生间调整至外墙边，或接受机械通风并降低推荐优先级。",
                measured_value=0.0,
            )
        )
    return issues


def _check_sliver_rooms(
    program: DesignProgram, candidate: LayoutCandidate
) -> list[GateIssue]:
    placements = _placement_map(candidate)
    issues: list[GateIssue] = []
    for room in program.rooms:
        p = placements.get(room.id)
        if p is None:
            continue
        area = p.rect.area
        if area < _SLIVER_MIN_AREA:
            continue
        ar = p.rect.aspect_ratio
        if ar < _SLIVER_ASPECT:
            continue
        issues.append(
            GateIssue(
                code="sliver_room",
                level=GateLevel.WARNING,
                title=f"「{_name(program, room.id)}」过于狭长",
                message=(
                    f"「{_name(program, room.id)}」长宽比约 {ar:.1f}，"
                    "空间可用性偏低。"
                ),
                room_ids=[room.id],
                recommended_action="调整切分比例，避免过窄条状房间。",
                measured_value=ar,
            )
        )
    return issues


def evaluate_architectural_gate(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> ArchitecturalGateResult:
    """对候选运行建筑质量门槛检查。"""
    ensure_access_graph(program)
    graph = build_realized_access_graph(program, candidate)

    blockers: list[GateIssue] = []
    warnings: list[GateIssue] = []
    preferences: list[GateIssue] = []

    for issue in (
        *_check_unreachable(program, candidate, graph),
        *_check_bedroom_chain(program, candidate),
        *_check_guest_bath_access(program, candidate, graph),
        *_check_entry_stair(program, candidate, graph),
        *_check_black_wet(program, candidate),
        *_check_sliver_rooms(program, candidate),
    ):
        if issue.level == GateLevel.BLOCKER:
            blockers.append(issue)
        elif issue.level == GateLevel.WARNING:
            warnings.append(issue)
        else:
            preferences.append(issue)

    return ArchitecturalGateResult(
        passed=len(blockers) == 0,
        blockers=blockers,
        warnings=warnings,
        preferences=preferences,
    )


def _issue_to_finding(issue: GateIssue) -> DesignFinding:
    if issue.level == GateLevel.BLOCKER:
        sev = FindingSeverity.PROBLEM
        category = EvaluationAxis.PRIVACY.value
        if issue.code in (
            "unreachable_rooms",
            "stair_unreachable",
            "entry_stair_via_private",
            "entry_stair_skips_foyer",
        ):
            category = EvaluationAxis.CIRCULATION.value
        elif issue.code == "black_wet":
            category = EvaluationAxis.ENVIRONMENT.value
    elif issue.level == GateLevel.WARNING:
        sev = FindingSeverity.WARNING
        category = EvaluationAxis.SPATIAL.value
        if issue.code == "black_wet":
            category = EvaluationAxis.ENVIRONMENT.value
        elif issue.code == "entry_stair_skips_foyer":
            category = EvaluationAxis.CIRCULATION.value
    else:
        sev = FindingSeverity.INFO
        category = EvaluationAxis.PROGRAM.value

    return finding(
        id=f"arch.gate.{issue.code}"
        + (f":{issue.room_ids[0]}" if issue.room_ids else ""),
        category=category,
        severity=sev,
        title=issue.title,
        message=issue.message,
        room_ids=list(issue.room_ids),
        metric=f"arch_gate.{issue.code}",
        measured_value=issue.measured_value,
        recommended_action=issue.recommended_action,
    )


def architectural_gate_findings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    result: ArchitecturalGateResult | None = None,
) -> list[DesignFinding]:
    gate = result or evaluate_architectural_gate(program, candidate)
    return [_issue_to_finding(i) for i in gate.all_issues]


def apply_architectural_gate_metrics(
    candidate: LayoutCandidate,
    gate: ArchitecturalGateResult,
) -> None:
    """写入候选 metrics，供选型过滤使用。"""
    candidate.metrics["architectural_gate_pass"] = gate.passed
    candidate.metrics["architectural_gate_blocker_count"] = len(gate.blockers)
    candidate.metrics["architectural_gate_warning_count"] = len(gate.warnings)
    candidate.metrics["architectural_gate_version"] = gate.version
    if gate.blockers:
        candidate.metrics["architectural_gate_blocker_codes"] = ",".join(
            sorted({b.code for b in gate.blockers})
        )

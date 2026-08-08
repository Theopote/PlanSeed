"""Circulation metrics + findings — Phase 2.3 / 3.5。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from packages.schema.scoring import DesignFinding, FindingSeverity
from solver.evaluation.findings import finding
from solver.topology.access import (
    ENTRY_NODE_ID,
    access_depths,
    build_realized_access_graph,
    occupied_room_ids,
    reachable_nodes,
)
from solver.topology.derive_access import ensure_access_graph


def _name(program: DesignProgram, room_id: str) -> str:
    if room_id == ENTRY_NODE_ID:
        return "主入口"
    if room_id.startswith("stair-"):
        return "楼梯"
    room = program.room_by_id(room_id)
    return room.name if room is not None else room_id


def _circulation_compatible(program: DesignProgram, room_id: str) -> bool:
    room = program.room_by_id(room_id)
    if room is None:
        return room_id.startswith("stair-") or room_id == ENTRY_NODE_ID
    if room.category == RoomCategory.CIRCULATION:
        return True
    if room.category == RoomCategory.PUBLIC:
        return True
    return False


def compute_circulation_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
) -> dict[str, float]:
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

    deg: dict[str, int] = {r: 0 for r in occupied}
    for c in graph.connections:
        if c.a in deg:
            deg[c.a] += 1
        if c.b in deg:
            deg[c.b] += 1
    dead = sum(1 for r, d in deg.items() if r in reached and d <= 1)

    through = 0
    for mid in list(reached):
        if _circulation_compatible(program, mid):
            continue
        if deg.get(mid, 0) >= 2 and depths.get(mid, 0) >= 2:
            room = program.room_by_id(mid)
            if room is not None and room.category in (
                RoomCategory.PRIVATE,
                RoomCategory.WET,
                RoomCategory.SERVICE,
            ):
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


def circulation_findings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    *,
    circ_metrics: dict[str, float],
    access_metrics: dict[str, float],
) -> list[DesignFinding]:
    ensure_access_graph(program)
    graph = build_realized_access_graph(program, candidate)
    occupied = occupied_room_ids(program)
    out: list[DesignFinding] = []

    # 入口连公共
    entry_rooms = [
        c.b if c.a == ENTRY_NODE_ID else c.a
        for c in graph.connections
        if ENTRY_NODE_ID in (c.a, c.b)
    ]
    public_hit = False
    for rid in entry_rooms:
        room = program.room_by_id(rid)
        if room is not None and room.category == RoomCategory.PUBLIC:
            public_hit = True
            out.append(
                finding(
                    id="circulation.entry_to_public",
                    category="circulation",
                    severity=FindingSeverity.POSITIVE,
                    title="主入口进入公共空间",
                    message=f"主入口直接连通「{_name(program, rid)}」，动线起点清晰。",
                    room_ids=[rid],
                    metric="entry_on_public",
                    measured_value=1.0,
                )
            )
            break
    if entry_rooms and not public_hit:
        first = entry_rooms[0]
        out.append(
            finding(
                id="circulation.entry_not_public",
                category="circulation",
                severity=FindingSeverity.WARNING,
                title="主入口未直接进入公共厅",
                message=(
                    f"主入口首先连通「{_name(program, first)}」，"
                    "建议优先连接门厅/客厅等公共空间。"
                ),
                room_ids=[first],
                recommended_action="调整 ExteriorEntry 贴边房间或门厅布置。",
            )
        )

    ratio = float(circ_metrics.get("reachable_ratio", 1.0))
    if ratio >= 1.0 - 1e-9:
        out.append(
            finding(
                id="circulation.all_reachable",
                category="circulation",
                severity=FindingSeverity.POSITIVE,
                title="全部占用房间可达",
                message="RealizedAccessGraph 上所有程序房间均可从主入口到达。",
                metric="reachable_ratio",
                measured_value=ratio,
            )
        )
    else:
        missing = occupied - reachable_nodes(graph, start=ENTRY_NODE_ID)
        names = "、".join(_name(program, r) for r in sorted(missing)[:5])
        out.append(
            finding(
                id="circulation.partial_reachable",
                category="circulation",
                severity=FindingSeverity.PROBLEM,
                title=f"可达率 {ratio:.0%}",
                message=f"部分房间不可达（含：{names}）。",
                room_ids=sorted(missing)[:8],
                metric="reachable_ratio",
                measured_value=ratio,
                recommended_action="补门洞或修复必连共边。",
            )
        )

    through = float(circ_metrics.get("through_room_count", 0.0))
    if through > 0:
        out.append(
            finding(
                id="circulation.through_room",
                category="circulation",
                severity=FindingSeverity.WARNING,
                title=f"潜在穿堂房间 ×{int(through)}",
                message=(
                    "若干私密/服务房间在 realized 图上度≥2，"
                    "可能被迫作为过道。"
                ),
                metric="through_room_count",
                measured_value=through,
                recommended_action="用走廊分流，避免卧室/卫生间成为必经节点。",
            )
        )

    avg_d = float(circ_metrics.get("average_access_depth", 0.0))
    max_d = float(circ_metrics.get("max_access_depth", 0.0))
    if max_d >= 4:
        deep = [
            r
            for r, d in access_depths(graph, start=ENTRY_NODE_ID).items()
            if r in occupied and d >= 4
        ]
        deep_names = "、".join(_name(program, r) for r in deep[:4])
        out.append(
            finding(
                id="circulation.deep_rooms",
                category="circulation",
                severity=FindingSeverity.WARNING,
                title=f"最大访问深度 {max_d:.0f}",
                message=(
                    f"平均深度 {avg_d:.1f}；深层房间包括：{deep_names or '—'}"
                ),
                room_ids=deep[:6],
                metric="max_access_depth",
                measured_value=max_d,
                recommended_action="缩短深层私密区到公共核的路径。",
            )
        )
    elif 1.5 <= avg_d <= 4.0 and ratio >= 1.0 - 1e-9:
        out.append(
            finding(
                id="circulation.depth_balanced",
                category="circulation",
                severity=FindingSeverity.POSITIVE,
                title="访问深度适中",
                message=f"平均访问深度 {avg_d:.1f}，交通层次较清晰。",
                metric="average_access_depth",
                measured_value=avg_d,
            )
        )

    pref = float(access_metrics.get("access_pref_satisfaction", 1.0))
    if pref < 0.5:
        out.append(
            finding(
                id="circulation.intent_weak",
                category="circulation",
                severity=FindingSeverity.WARNING,
                title=f"通行意图共边率 {pref:.0%}",
                message="AccessIntent 开口边中具备共边的比例偏低。",
                metric="access_pref_satisfaction",
                measured_value=pref,
                recommended_action="提高必连/偏好边的共边机会（打包序或局部修补）。",
            )
        )
    elif pref >= 0.85:
        out.append(
            finding(
                id="circulation.intent_strong",
                category="circulation",
                severity=FindingSeverity.POSITIVE,
                title="通行意图共边良好",
                message=f"AccessIntent 开口边共边满足率 {pref:.0%}。",
                metric="access_pref_satisfaction",
                measured_value=pref,
            )
        )

    # 楼梯连通
    stair_ids = [
        p.room_id
        for fl in candidate.floors
        for p in fl.placements
        if p.room_id.startswith("stair-")
    ]
    if stair_ids:
        reached = reachable_nodes(graph, start=ENTRY_NODE_ID)
        if any(s in reached for s in stair_ids):
            out.append(
                finding(
                    id="circulation.stair_linked",
                    category="circulation",
                    severity=FindingSeverity.POSITIVE,
                    title="楼梯接入交通网络",
                    message="楼梯核可从主入口经 realized 连接到达，竖向交通连贯。",
                    room_ids=stair_ids[:2],
                )
            )

    return out


def layout_stability_findings(
    circ_metrics: dict[str, float],
    candidate: LayoutCandidate,
) -> list[DesignFinding]:
    score = float(circ_metrics.get("layout_stability_score", 100.0))
    repairs = float(candidate.metrics.get("connection_repairs", 0) or 0)
    reslices = float(candidate.metrics.get("connection_reslices", 0) or 0)
    out: list[DesignFinding] = []
    if repairs <= 0 and reslices <= 0:
        out.append(
            finding(
                id="stability.clean_generation",
                category="layout_stability",
                severity=FindingSeverity.POSITIVE,
                title="原始生成即成立",
                message="未依赖 ConnectionResolver 修补/重切即可形成共边开口。",
                metric="layout_stability_score",
                measured_value=score,
            )
        )
    elif score < 85 or reslices >= 2:
        out.append(
            finding(
                id="stability.heavy_repair",
                category="layout_stability",
                severity=FindingSeverity.WARNING,
                title="依赖较多局部修补",
                message=(
                    f"connection_repairs={int(repairs)}, "
                    f"reslices={int(reslices)}；方案经修补才成立。"
                ),
                metric="layout_stability_score",
                measured_value=score,
                recommended_action="改进拓扑打包，减少事后缝隙修补。",
            )
        )
    else:
        out.append(
            finding(
                id="stability.light_repair",
                category="layout_stability",
                severity=FindingSeverity.INFO,
                title="轻微局部修补",
                message=(
                    f"经 {int(repairs)} 次修补"
                    f"（含 {int(reslices)} 次重切）后成立。"
                ),
                metric="layout_stability_score",
                measured_value=score,
            )
        )
    return out

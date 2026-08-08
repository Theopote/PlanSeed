"""Circulation metrics + findings (Circulation / Robustness axes)."""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.room import RoomCategory
from packages.schema.scoring import DesignFinding, EvaluationAxis, FindingSeverity
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
        return "\u4e3b\u5165\u53e3"
    if room_id.startswith("stair-"):
        return "\u697c\u68af"
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
    axis = EvaluationAxis.CIRCULATION.value

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
                    category=axis,
                    severity=FindingSeverity.POSITIVE,
                    title="\u4e3b\u5165\u53e3\u8fdb\u5165\u516c\u5171\u7a7a\u95f4",
                    message=(
                        f"\u4e3b\u5165\u53e3\u76f4\u63a5\u8fde\u901a\u300c{_name(program, rid)}\u300d\uff0c"
                        "\u52a8\u7ebf\u8d77\u70b9\u6e05\u6670\u3002"
                    ),
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
                category=axis,
                severity=FindingSeverity.WARNING,
                title="\u4e3b\u5165\u53e3\u672a\u76f4\u63a5\u8fdb\u5165\u516c\u5171\u5385",
                message=(
                    f"\u4e3b\u5165\u53e3\u9996\u5148\u8fde\u901a\u300c{_name(program, first)}\u300d\uff0c"
                    "\u5efa\u8bae\u4f18\u5148\u8fde\u63a5\u95e8\u5385/\u5ba2\u5385\u7b49\u516c\u5171\u7a7a\u95f4\u3002"
                ),
                room_ids=[first],
                recommended_action=(
                    "\u8c03\u6574 ExteriorEntry \u8d34\u8fb9\u623f\u95f4\u6216\u95e8\u5385\u5e03\u7f6e\u3002"
                ),
            )
        )

    ratio = float(circ_metrics.get("reachable_ratio", 1.0))
    if ratio >= 1.0 - 1e-9:
        out.append(
            finding(
                id="circulation.all_reachable",
                category=axis,
                severity=FindingSeverity.POSITIVE,
                title="\u5168\u90e8\u5360\u7528\u623f\u95f4\u53ef\u8fbe",
                message=(
                    "??????????????????????"
                    "?????????????"
                ),
                metric="reachable_ratio",
                measured_value=ratio,
            )
        )
    else:
        missing = occupied - reachable_nodes(graph, start=ENTRY_NODE_ID)
        names = "\u3001".join(_name(program, r) for r in sorted(missing)[:5])
        out.append(
            finding(
                id="circulation.partial_reachable",
                category=axis,
                severity=FindingSeverity.PROBLEM,
                title=f"\u53ef\u8fbe\u7387 {ratio:.0%}",
                message=f"\u90e8\u5206\u623f\u95f4\u4e0d\u53ef\u8fbe\uff08\u542b\uff1a{names}\uff09\u3002",
                room_ids=sorted(missing)[:8],
                metric="reachable_ratio",
                measured_value=ratio,
                recommended_action="\u8865\u95e8\u6d1e\u6216\u4fee\u590d\u5fc5\u8fde\u5171\u8fb9\u3002",
            )
        )

    through = float(circ_metrics.get("through_room_count", 0.0))
    if through > 0:
        out.append(
            finding(
                id="circulation.through_room",
                category=axis,
                severity=FindingSeverity.WARNING,
                title=f"\u6f5c\u5728\u7a7f\u5802\u623f\u95f4 x{int(through)}",
                message=(
                    "\u82e5\u5e72\u79c1\u5bc6/\u670d\u52a1\u623f\u95f4\u5728 realized \u56fe\u4e0a\u5ea6>=2\uff0c"
                    "\u53ef\u80fd\u88ab\u8feb\u4f5c\u4e3a\u8fc7\u9053\u3002"
                ),
                metric="through_room_count",
                measured_value=through,
                recommended_action=(
                    "\u7528\u8d70\u5eca\u5206\u6d41\uff0c\u907f\u514d\u5367\u5ba4/\u536b\u751f\u95f4"
                    "\u6210\u4e3a\u5fc5\u7ecf\u8282\u70b9\u3002"
                ),
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
        deep_names = "\u3001".join(_name(program, r) for r in deep[:4])
        out.append(
            finding(
                id="circulation.deep_rooms",
                category=axis,
                severity=FindingSeverity.WARNING,
                title=f"\u6700\u5927\u8bbf\u95ee\u6df1\u5ea6 {max_d:.0f}",
                message=(
                    f"\u5e73\u5747\u6df1\u5ea6 {avg_d:.1f}\uff1b"
                    f"\u6df1\u5c42\u623f\u95f4\u5305\u62ec\uff1a{deep_names or '-'}"
                ),
                room_ids=deep[:6],
                metric="max_access_depth",
                measured_value=max_d,
                recommended_action=(
                    "\u7f29\u77ed\u6df1\u5c42\u79c1\u5bc6\u533a\u5230\u516c\u5171\u6838\u7684\u8def\u5f84\u3002"
                ),
            )
        )
    elif 1.5 <= avg_d <= 4.0 and ratio >= 1.0 - 1e-9:
        out.append(
            finding(
                id="circulation.depth_balanced",
                category=axis,
                severity=FindingSeverity.POSITIVE,
                title="\u8bbf\u95ee\u6df1\u5ea6\u9002\u4e2d",
                message=(
                    f"\u5e73\u5747\u8bbf\u95ee\u6df1\u5ea6 {avg_d:.1f}\uff0c"
                    "\u4ea4\u901a\u5c42\u6b21\u8f83\u6e05\u6670\u3002"
                ),
                metric="average_access_depth",
                measured_value=avg_d,
            )
        )

    pref = float(access_metrics.get("access_pref_satisfaction", 1.0))
    if pref < 0.5:
        out.append(
            finding(
                id="circulation.intent_weak",
                category=axis,
                severity=FindingSeverity.WARNING,
                title=f"\u901a\u884c\u610f\u56fe\u5171\u8fb9\u7387 {pref:.0%}",
                message=(
                    "AccessIntent \u5f00\u53e3\u8fb9\u4e2d\u5177\u5907\u5171\u8fb9"
                    "\u7684\u6bd4\u4f8b\u504f\u4f4e\u3002"
                ),
                metric="access_pref_satisfaction",
                measured_value=pref,
                recommended_action=(
                    "\u63d0\u9ad8\u5fc5\u8fde/\u504f\u597d\u8fb9\u7684\u5171\u8fb9\u673a\u4f1a"
                    "\uff08\u6253\u5305\u5e8f\u6216\u5c40\u90e8\u4fee\u8865\uff09\u3002"
                ),
            )
        )
    elif pref >= 0.85:
        out.append(
            finding(
                id="circulation.intent_strong",
                category=axis,
                severity=FindingSeverity.POSITIVE,
                title="\u901a\u884c\u610f\u56fe\u5171\u8fb9\u826f\u597d",
                message=(
                    f"AccessIntent \u5f00\u53e3\u8fb9\u5171\u8fb9\u6ee1\u8db3\u7387 "
                    f"{pref:.0%}\u3002"
                ),
                metric="access_pref_satisfaction",
                measured_value=pref,
            )
        )

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
                    category=axis,
                    severity=FindingSeverity.POSITIVE,
                    title="\u697c\u68af\u63a5\u5165\u4ea4\u901a\u7f51\u7edc",
                    message=(
                        "\u697c\u68af\u6838\u53ef\u4ece\u4e3b\u5165\u53e3\u7ecf realized "
                        "\u8fde\u63a5\u5230\u8fbe\uff0c\u7ad6\u5411\u4ea4\u901a\u8fde\u8d2f\u3002"
                    ),
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
    axis = EvaluationAxis.ROBUSTNESS.value
    if repairs <= 0 and reslices <= 0:
        out.append(
            finding(
                id="robustness.clean_generation",
                category=axis,
                severity=FindingSeverity.POSITIVE,
                title="\u539f\u59cb\u751f\u6210\u5373\u6210\u7acb",
                message=(
                    "\u672a\u4f9d\u8d56 ConnectionResolver \u4fee\u8865/\u91cd\u5207"
                    "\u5373\u53ef\u5f62\u6210\u5171\u8fb9\u5f00\u53e3\u3002"
                ),
                metric="layout_stability_score",
                measured_value=score,
            )
        )
    elif score < 85 or reslices >= 2:
        out.append(
            finding(
                id="robustness.heavy_repair",
                category=axis,
                severity=FindingSeverity.WARNING,
                title="\u4f9d\u8d56\u8f83\u591a\u5c40\u90e8\u4fee\u8865",
                message=(
                    f"connection_repairs={int(repairs)}, "
                    f"reslices={int(reslices)}\uff1b"
                    "\u65b9\u6848\u7ecf\u4fee\u8865\u624d\u6210\u7acb\u3002"
                ),
                metric="layout_stability_score",
                measured_value=score,
                recommended_action=(
                    "\u6539\u8fdb\u62d3\u6251\u6253\u5305\uff0c"
                    "\u51cf\u5c11\u4e8b\u540e\u7f1d\u9699\u4fee\u8865\u3002"
                ),
            )
        )
    else:
        out.append(
            finding(
                id="robustness.light_repair",
                category=axis,
                severity=FindingSeverity.INFO,
                title="\u8f7b\u5fae\u5c40\u90e8\u4fee\u8865",
                message=(
                    f"\u7ecf {int(repairs)} \u6b21\u4fee\u8865"
                    f"\uff08\u542b {int(reslices)} \u6b21\u91cd\u5207\uff09"
                    "\u540e\u6210\u7acb\u3002"
                ),
                metric="layout_stability_score",
                measured_value=score,
            )
        )
    return out

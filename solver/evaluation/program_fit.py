"""ProgramFit / SpaceEfficiency — Phase 3 + Metric Ownership（3.5）。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.scoring import DesignFinding, FindingSeverity
from solver.evaluation.findings import finding
from solver.evaluation.geometry import compute_geometry_metrics
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights


def compute_program_fit_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, float]:
    """
    程序符合度（owner：coverage + area_accuracy）。

    area_accuracy 只在此计入总分，不再进入 geometry_score。
    """
    geo = compute_geometry_metrics(program, candidate, weights)
    placed = {
        p.room_id
        for fl in candidate.floors
        for p in fl.placements
        if not p.room_id.startswith("stair-")
    }
    needed = {r.id for r in program.rooms}
    coverage = len(needed & placed) / len(needed) if needed else 1.0
    area_acc = float(geo.get("area_accuracy", 1.0))
    return {
        "program_coverage": round(coverage, 4),
        "program_area_accuracy": round(area_acc, 4),
        "program_fit": round(0.45 * coverage + 0.55 * area_acc, 4),
    }


def program_fit_score(metrics: dict[str, float]) -> float:
    return max(0.0, min(100.0, float(metrics.get("program_fit", 1.0)) * 100.0))


def compute_space_efficiency_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, float]:
    """
    空间效率（owner：compactness / perimeter efficiency）。

    slender 只读展示，不计分（owner = geometry）。
    """
    geo = compute_geometry_metrics(program, candidate, weights)
    compactness = float(geo.get("compactness", 1.0))
    slender = float(geo.get("slender_room_count", 0))
    n = max(1, len(program.rooms))
    slender_ratio = slender / n
    return {
        "space_compactness": round(compactness, 4),
        "slender_room_ratio": round(slender_ratio, 4),  # 只读；不计 space_efficiency
        "space_efficiency": round(max(0.0, min(1.0, compactness)), 4),
    }


def space_efficiency_score(metrics: dict[str, float]) -> float:
    return max(
        0.0, min(100.0, float(metrics.get("space_efficiency", 1.0)) * 100.0)
    )


def program_fit_findings(
    program: DesignProgram,
    candidate: LayoutCandidate,
    fit_m: dict[str, float],
    eff_m: dict[str, float],
    geo_m: dict[str, float | int],
) -> list[DesignFinding]:
    out: list[DesignFinding] = []
    cov = float(fit_m.get("program_coverage", 1.0))
    if cov >= 1.0 - 1e-9:
        out.append(
            finding(
                id="program_fit.full_coverage",
                category="program_fit",
                severity=FindingSeverity.POSITIVE,
                title="程序房间全部落下",
                message=f"共 {len(program.rooms)} 个程序房间均有放置。",
                metric="program_coverage",
                measured_value=cov,
            )
        )
    else:
        placed = {
            p.room_id
            for fl in candidate.floors
            for p in fl.placements
            if not p.room_id.startswith("stair-")
        }
        missing = [r.id for r in program.rooms if r.id not in placed]
        out.append(
            finding(
                id="program_fit.missing_rooms",
                category="program_fit",
                severity=FindingSeverity.PROBLEM,
                title=f"覆盖率 {cov:.0%}",
                message=f"未放置房间：{', '.join(missing[:6])}。",
                room_ids=missing[:8],
                metric="program_coverage",
                measured_value=cov,
                recommended_action="检查楼层归属与打包失败原因。",
            )
        )

    area_acc = float(fit_m.get("program_area_accuracy", 1.0))
    if area_acc >= 0.85:
        out.append(
            finding(
                id="program_fit.area_share_ok",
                category="program_fit",
                severity=FindingSeverity.POSITIVE,
                title="面积份额较一致",
                message=f"面积份额准确度 {area_acc:.0%}（相对目标权重）。",
                metric="program_area_accuracy",
                measured_value=area_acc,
            )
        )
    elif area_acc < 0.6:
        out.append(
            finding(
                id="program_fit.area_share_weak",
                category="program_fit",
                severity=FindingSeverity.WARNING,
                title=f"面积份额偏差大（{area_acc:.0%}）",
                message="实际房间面积份额与目标权重偏差较大。",
                metric="program_area_accuracy",
                measured_value=area_acc,
                recommended_action="调整目标面积权重或切分策略。",
            )
        )

    slender = int(geo_m.get("slender_room_count", 0) or 0)
    if slender > 0:
        out.append(
            finding(
                id="geometry.slender_rooms",
                category="geometry",
                severity=FindingSeverity.WARNING,
                title=f"{slender} 个房间偏细长",
                message="部分房间长宽比超过阈值，可能影响家具布置。",
                metric="slender_room_count",
                measured_value=float(slender),
                recommended_action="提高切分正方形倾向或约束最小短边。",
            )
        )

    compact = float(eff_m.get("space_compactness", eff_m.get("space_efficiency", 1.0)))
    if compact >= 0.75:
        out.append(
            finding(
                id="space_efficiency.compact",
                category="space_efficiency",
                severity=FindingSeverity.POSITIVE,
                title="平面外轮廓较紧凑",
                message=f"场地周长效率（compactness）{compact:.0%}。",
                metric="compactness",
                measured_value=compact,
            )
        )
    elif compact < 0.55:
        out.append(
            finding(
                id="space_efficiency.sprawling",
                category="space_efficiency",
                severity=FindingSeverity.WARNING,
                title="平面外轮廓偏松散",
                message=f"compactness={compact:.0%}，外墙周长相对占地效率偏低。",
                metric="compactness",
                measured_value=compact,
                recommended_action="收紧 footprint 或减少凹凸。",
            )
        )
    return out

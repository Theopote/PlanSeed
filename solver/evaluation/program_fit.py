"""ProgramFit / SpaceEfficiency (Program / Spatial axes)."""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from packages.schema.scoring import DesignFinding, EvaluationAxis, FindingSeverity
from solver.evaluation.findings import finding
from solver.evaluation.geometry import compute_geometry_metrics
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights


def compute_program_fit_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, float]:
    """coverage + area_accuracy -> Program axis only."""
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
    """compactness -> Spatial axis; slender is display-only."""
    geo = compute_geometry_metrics(program, candidate, weights)
    compactness = float(geo.get("compactness", 1.0))
    slender = float(geo.get("slender_room_count", 0))
    n = max(1, len(program.rooms))
    slender_ratio = slender / n
    return {
        "space_compactness": round(compactness, 4),
        "slender_room_ratio": round(slender_ratio, 4),
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
                id="program.full_coverage",
                category=EvaluationAxis.PROGRAM.value,
                severity=FindingSeverity.POSITIVE,
                title="\u7a0b\u5e8f\u623f\u95f4\u5168\u90e8\u843d\u4e0b",
                message=(
                    f"\u5171 {len(program.rooms)} "
                    "\u4e2a\u7a0b\u5e8f\u623f\u95f4\u5747\u6709\u653e\u7f6e\u3002"
                ),
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
                id="program.missing_rooms",
                category=EvaluationAxis.PROGRAM.value,
                severity=FindingSeverity.PROBLEM,
                title=f"\u8986\u76d6\u7387 {cov:.0%}",
                message=(
                    f"\u672a\u653e\u7f6e\u623f\u95f4\uff1a{', '.join(missing[:6])}\u3002"
                ),
                room_ids=missing[:8],
                metric="program_coverage",
                measured_value=cov,
                recommended_action=(
                    "\u68c0\u67e5\u697c\u5c42\u5f52\u5c5e\u4e0e\u6253\u5305\u5931\u8d25\u539f\u56e0\u3002"
                ),
            )
        )

    area_acc = float(fit_m.get("program_area_accuracy", 1.0))
    if area_acc >= 0.85:
        out.append(
            finding(
                id="program.area_share_ok",
                category=EvaluationAxis.PROGRAM.value,
                severity=FindingSeverity.POSITIVE,
                title="\u9762\u79ef\u4efd\u989d\u8f83\u4e00\u81f4",
                message=(
                    f"\u9762\u79ef\u4efd\u989d\u51c6\u786e\u5ea6 {area_acc:.0%}"
                    "\uff08\u76f8\u5bf9\u76ee\u6807\u6743\u91cd\uff09\u3002"
                ),
                metric="program_area_accuracy",
                measured_value=area_acc,
            )
        )
    elif area_acc < 0.6:
        out.append(
            finding(
                id="program.area_share_weak",
                category=EvaluationAxis.PROGRAM.value,
                severity=FindingSeverity.WARNING,
                title=f"\u9762\u79ef\u4efd\u989d\u504f\u5dee\u5927\uff08{area_acc:.0%}\uff09",
                message=(
                    "\u5b9e\u9645\u623f\u95f4\u9762\u79ef\u4efd\u989d\u4e0e\u76ee\u6807"
                    "\u6743\u91cd\u504f\u5dee\u8f83\u5927\u3002"
                ),
                metric="program_area_accuracy",
                measured_value=area_acc,
                recommended_action=(
                    "\u8c03\u6574\u76ee\u6807\u9762\u79ef\u6743\u91cd\u6216\u5207\u5206\u7b56\u7565\u3002"
                ),
            )
        )

    slender = int(geo_m.get("slender_room_count", 0) or 0)
    if slender > 0:
        out.append(
            finding(
                id="spatial.slender_rooms",
                category=EvaluationAxis.SPATIAL.value,
                severity=FindingSeverity.WARNING,
                title=f"{slender} \u4e2a\u623f\u95f4\u504f\u7ec6\u957f",
                message=(
                    "\u90e8\u5206\u623f\u95f4\u957f\u5bbd\u6bd4\u8d85\u8fc7\u9608\u503c\uff0c"
                    "\u53ef\u80fd\u5f71\u54cd\u5bb6\u5177\u5e03\u7f6e\u3002"
                ),
                metric="slender_room_count",
                measured_value=float(slender),
                recommended_action=(
                    "\u63d0\u9ad8\u5207\u5206\u6b63\u65b9\u5f62\u503e\u5411\u6216"
                    "\u7ea6\u675f\u6700\u5c0f\u77ed\u8fb9\u3002"
                ),
            )
        )

    compact = float(eff_m.get("space_compactness", eff_m.get("space_efficiency", 1.0)))
    if compact >= 0.75:
        out.append(
            finding(
                id="spatial.compact",
                category=EvaluationAxis.SPATIAL.value,
                severity=FindingSeverity.POSITIVE,
                title="\u5e73\u9762\u5916\u8f6e\u5ed3\u8f83\u7d27\u51d1",
                message=f"\u573a\u5730\u5468\u957f\u6548\u7387\uff08compactness\uff09{compact:.0%}\u3002",
                metric="compactness",
                measured_value=compact,
            )
        )
    elif compact < 0.55:
        out.append(
            finding(
                id="spatial.sprawling",
                category=EvaluationAxis.SPATIAL.value,
                severity=FindingSeverity.WARNING,
                title="\u5e73\u9762\u5916\u8f6e\u5ed3\u504f\u677e\u6563",
                message=(
                    f"compactness={compact:.0%}\uff0c"
                    "\u5916\u5899\u5468\u957f\u76f8\u5bf9\u5360\u5730\u6548\u7387\u504f\u4f4e\u3002"
                ),
                metric="compactness",
                measured_value=compact,
                recommended_action="\u6536\u7d27 footprint \u6216\u51cf\u5c11\u51f9\u51f8\u3002",
            )
        )
    return out

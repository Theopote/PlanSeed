"""ProgramFit / SpaceEfficiency — Phase 3 建筑评价切片。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.program import DesignProgram
from solver.evaluation.geometry import compute_geometry_metrics
from solver.evaluation.weights import DEFAULT_WEIGHTS, ScoreWeights


def compute_program_fit_metrics(
    program: DesignProgram,
    candidate: LayoutCandidate,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> dict[str, float]:
    """程序符合度：面积份额 + 房间是否都落下。"""
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
    geo = compute_geometry_metrics(program, candidate, weights)
    compactness = float(geo.get("compactness", 1.0))
    slender = float(geo.get("slender_room_count", 0))
    n = max(1, len(program.rooms))
    slender_ratio = slender / n
    # 紧凑好、细长差
    eff = compactness * (1.0 - 0.5 * slender_ratio)
    return {
        "space_compactness": round(compactness, 4),
        "slender_room_ratio": round(slender_ratio, 4),
        "space_efficiency": round(max(0.0, min(1.0, eff)), 4),
    }


def space_efficiency_score(metrics: dict[str, float]) -> float:
    return max(
        0.0, min(100.0, float(metrics.get("space_efficiency", 1.0)) * 100.0)
    )

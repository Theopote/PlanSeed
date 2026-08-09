"""Phase 8.2 — Pareto / non-dominated selection（静态前沿，非 GA）。

目标轴（均为越高越好）：
  Efficiency ← spatial_score
  Privacy    ← privacy_score
  Circulation← circulation_score
  Environment← environment_score

从已有候选中取非支配集；用拥挤距离在前沿上截断到 top_k。
禁止 NSGA-II / 遗传搜索生成新几何。
"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate

# (evaluation 字段, role 片段, 短标签)
PARETO_OBJECTIVES: tuple[tuple[str, str, str], ...] = (
    ("spatial_score", "efficiency", "效率更好"),
    ("privacy_score", "privacy", "隐私更好"),
    ("circulation_score", "circulation", "流线更好"),
    ("environment_score", "environment", "朝向更好"),
)


def _axis_value(candidate: LayoutCandidate, key: str) -> float:
    ev = candidate.evaluation
    if ev is None:
        return float(candidate.metrics.get(key, 0.0) or 0.0)
    return float(getattr(ev, key, 0.0) or 0.0)


def objective_vector(
    candidate: LayoutCandidate,
    *,
    objectives: tuple[tuple[str, str, str], ...] = PARETO_OBJECTIVES,
) -> tuple[float, ...]:
    return tuple(_axis_value(candidate, key) for key, _role, _label in objectives)


def dominates(
    a: LayoutCandidate,
    b: LayoutCandidate,
    *,
    objectives: tuple[tuple[str, str, str], ...] = PARETO_OBJECTIVES,
    eps: float = 1e-9,
) -> bool:
    """a 支配 b：所有目标 ≥ 且至少一维严格更好。"""
    va = objective_vector(a, objectives=objectives)
    vb = objective_vector(b, objectives=objectives)
    ge_all = all(x + eps >= y for x, y in zip(va, vb, strict=True))
    gt_any = any(x > y + eps for x, y in zip(va, vb, strict=True))
    return ge_all and gt_any


def pareto_front(
    candidates: list[LayoutCandidate],
    *,
    objectives: tuple[tuple[str, str, str], ...] = PARETO_OBJECTIVES,
) -> list[LayoutCandidate]:
    """返回非支配候选（保持输入相对顺序中的稳定：先按总分再筛）。"""
    valid = [
        c
        for c in candidates
        if c.validation and c.validation.valid and c.score is not None
    ]
    valid.sort(key=lambda c: c.score or 0.0, reverse=True)
    front: list[LayoutCandidate] = []
    for c in valid:
        if any(dominates(other, c, objectives=objectives) for other in valid if other.id != c.id):
            continue
        front.append(c)
    return front


def crowding_distances(
    front: list[LayoutCandidate],
    *,
    objectives: tuple[tuple[str, str, str], ...] = PARETO_OBJECTIVES,
) -> dict[str, float]:
    """NSGA-II 风格拥挤距离（仅用于前沿截断，不进化）。"""
    n = len(front)
    if n == 0:
        return {}
    dist = {c.id: 0.0 for c in front}
    if n <= 2:
        for c in front:
            dist[c.id] = float("inf")
        return dist

    for dim, (_key, _role, _label) in enumerate(objectives):
        ordered = sorted(front, key=lambda c: objective_vector(c, objectives=objectives)[dim])
        dist[ordered[0].id] = float("inf")
        dist[ordered[-1].id] = float("inf")
        lo = objective_vector(ordered[0], objectives=objectives)[dim]
        hi = objective_vector(ordered[-1], objectives=objectives)[dim]
        span = hi - lo
        if span <= 1e-12:
            continue
        for i in range(1, n - 1):
            prev_v = objective_vector(ordered[i - 1], objectives=objectives)[dim]
            next_v = objective_vector(ordered[i + 1], objectives=objectives)[dim]
            dist[ordered[i].id] += (next_v - prev_v) / span
    return dist


def _tradeoff_label(
    candidate: LayoutCandidate,
    front: list[LayoutCandidate],
    *,
    objectives: tuple[tuple[str, str, str], ...] = PARETO_OBJECTIVES,
) -> str:
    strengths: list[str] = []
    for key, _role, label in objectives:
        best = max(_axis_value(o, key) for o in front)
        if _axis_value(candidate, key) + 1e-9 >= best:
            strengths.append(label)
    if not strengths:
        return "权衡前沿"
    # 最多展示两轴，避免标签过长
    return " · ".join(strengths[:2])


def _tag(candidate: LayoutCandidate, *, label: str, front_size: int) -> None:
    candidate.metrics["selection_role"] = "pareto"
    candidate.metrics["selection_label"] = label
    candidate.metrics["pareto_front"] = True
    candidate.metrics["pareto_front_size"] = front_size


def select_pareto_frontier(
    candidates: list[LayoutCandidate],
    top_k: int,
    *,
    objectives: tuple[tuple[str, str, str], ...] = PARETO_OBJECTIVES,
) -> list[LayoutCandidate]:
    """
    非支配集 → 拥挤距离截断到 top_k → 打权衡标签。

    前沿不足时按总分从剩余 valid 补齐（role=diverse）。
    """
    if top_k <= 0:
        return []

    valid = [
        c
        for c in candidates
        if c.validation and c.validation.valid and c.score is not None
    ]
    if not valid:
        return []

    front = pareto_front(valid, objectives=objectives)
    front_size = len(front)

    if len(front) > top_k:
        crowd = crowding_distances(front, objectives=objectives)
        # 拥挤优先；同分看总分
        front = sorted(
            front,
            key=lambda c: (crowd.get(c.id, 0.0), c.score or 0.0),
            reverse=True,
        )[:top_k]
    else:
        # 稳定：前沿内按总分
        front = sorted(front, key=lambda c: c.score or 0.0, reverse=True)

    selected: list[LayoutCandidate] = []
    selected_ids: set[str] = set()
    for c in front:
        _tag(c, label=_tradeoff_label(c, front, objectives=objectives), front_size=front_size)
        selected.append(c)
        selected_ids.add(c.id)

    if len(selected) < top_k:
        rest = sorted(
            (c for c in valid if c.id not in selected_ids),
            key=lambda c: c.score or 0.0,
            reverse=True,
        )
        for c in rest:
            if len(selected) >= top_k:
                break
            c.metrics["selection_role"] = "diverse"
            c.metrics["selection_label"] = "几何/分数补齐"
            c.metrics["pareto_front"] = False
            selected.append(c)
            selected_ids.add(c.id)

    return selected[:top_k]

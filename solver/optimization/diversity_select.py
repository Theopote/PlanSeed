"""Phase 8.1 — top-score + axis narrative alternatives（先于 Pareto）。

不是非支配集：先锁定最高总分，再按流线 / 隐私 / 朝向等轴挑「明显更好」的替代，
最后用几何 diversity 填满 top_k。
"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from solver.optimization.rank import layout_similarity

# 轴分须比「最高总分」候选高出此值，才有资格当叙事替代
DEFAULT_AXIS_MARGIN = 2.0

# (evaluation 字段, role id, UI 短标签)
ALTERNATIVE_AXES: tuple[tuple[str, str, str], ...] = (
    ("circulation_score", "circulation", "流线更好"),
    ("privacy_score", "privacy", "隐私更好"),
    ("environment_score", "environment", "朝向更好"),
)


def _axis_value(candidate: LayoutCandidate, key: str) -> float:
    ev = candidate.evaluation
    if ev is None:
        return float(candidate.metrics.get(key, 0.0) or 0.0)
    if key == "total_score":
        return float(ev.total_score)
    return float(getattr(ev, key, 0.0) or 0.0)


def _tag(candidate: LayoutCandidate, role: str, label: str) -> None:
    candidate.metrics["selection_role"] = role
    candidate.metrics["selection_label"] = label


def _is_similar(
    candidate: LayoutCandidate,
    selected: list[LayoutCandidate],
    *,
    min_diversity_threshold: float,
    buildable_width: float | None,
    buildable_depth: float | None,
) -> bool:
    return any(
        layout_similarity(
            candidate,
            s,
            buildable_width=buildable_width,
            buildable_depth=buildable_depth,
        )
        >= min_diversity_threshold
        for s in selected
    )


def select_diverse_alternatives(
    candidates: list[LayoutCandidate],
    top_k: int,
    *,
    min_diversity_threshold: float,
    buildable_width: float | None = None,
    buildable_depth: float | None = None,
    axis_margin: float = DEFAULT_AXIS_MARGIN,
    alternative_axes: tuple[tuple[str, str, str], ...] = ALTERNATIVE_AXES,
) -> list[LayoutCandidate]:
    """
    返回最多 top_k 个 valid 候选：

    1. 最高总分 → role=top_score
    2. 各叙事轴上相对 top 有明显优势、且几何不雷同 → circulation / privacy / …
    3. 其余按总分序用几何 diversity 补齐 → diverse
    """
    if top_k <= 0:
        return []

    valid = [
        c
        for c in candidates
        if c.validation and c.validation.valid and c.score is not None
    ]
    valid.sort(key=lambda c: c.score or 0.0, reverse=True)
    if not valid:
        return []

    selected: list[LayoutCandidate] = []
    selected_ids: set[str] = set()

    top = valid[0]
    _tag(top, "top_score", "最高总分")
    selected.append(top)
    selected_ids.add(top.id)

    for axis_key, role, label in alternative_axes:
        if len(selected) >= top_k:
            break
        top_axis = _axis_value(top, axis_key)
        best: LayoutCandidate | None = None
        best_val = float("-inf")
        for c in valid:
            if c.id in selected_ids:
                continue
            v = _axis_value(c, axis_key)
            if v + 1e-9 < top_axis + axis_margin:
                continue
            if _is_similar(
                c,
                selected,
                min_diversity_threshold=min_diversity_threshold,
                buildable_width=buildable_width,
                buildable_depth=buildable_depth,
            ):
                continue
            if v > best_val + 1e-9 or (
                abs(v - best_val) <= 1e-9
                and (c.score or 0.0) > (best.score or 0.0 if best else 0.0)
            ):
                best = c
                best_val = v
        if best is not None:
            _tag(best, role, label)
            selected.append(best)
            selected_ids.add(best.id)

    # 几何 diversity 填满
    if len(selected) < top_k:
        for c in valid:
            if len(selected) >= top_k:
                break
            if c.id in selected_ids:
                continue
            if _is_similar(
                c,
                selected,
                min_diversity_threshold=min_diversity_threshold,
                buildable_width=buildable_width,
                buildable_depth=buildable_depth,
            ):
                continue
            _tag(c, "diverse", "几何多样")
            selected.append(c)
            selected_ids.add(c.id)

    # 仍不足：忽略几何门槛，按分数补齐
    if len(selected) < top_k:
        for c in valid:
            if len(selected) >= top_k:
                break
            if c.id in selected_ids:
                continue
            _tag(c, "diverse", "几何多样")
            selected.append(c)
            selected_ids.add(c.id)

    return selected[:top_k]


def describe_selection(candidate: LayoutCandidate) -> str | None:
    """读出 selection_label（若有）。"""
    label = candidate.metrics.get("selection_label")
    return str(label) if label else None

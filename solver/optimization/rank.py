"""候选排序 — score + 轴叙事替代 + 可选几何 diversity（LayoutSignature）。"""

from __future__ import annotations

from packages.schema.identity import selection_version_for
from packages.schema.layout import LayoutCandidate
from packages.schema.signature import build_layout_signature, signature_similarity

DEFAULT_MIN_DIVERSITY_THRESHOLD = 0.85
# Alpha 默认：8.1 axis（非 Pareto）。Pareto 须显式 rank_mode="pareto"。
DEFAULT_RANK_MODE = "axis"


def layout_similarity(
    a: LayoutCandidate,
    b: LayoutCandidate,
    *,
    buildable_width: float | None = None,
    buildable_depth: float | None = None,
) -> float:
    """
    两候选布局相似度 [0, 1]。

    使用 buildable 归一化的 LayoutSignature（dx/W, dy/D, …）。
    """
    bw, bd = buildable_width, buildable_depth
    if bw is None or bd is None:
        bw, bd = _infer_buildable_size(a)
    sig_a = build_layout_signature(a, buildable_width=bw, buildable_depth=bd)
    sig_b = build_layout_signature(b, buildable_width=bw, buildable_depth=bd)
    return signature_similarity(sig_a, sig_b)


def _infer_buildable_size(candidate: LayoutCandidate) -> tuple[float, float]:
    max_r = 1.0
    max_b = 1.0
    for fl in candidate.floors:
        for p in fl.placements:
            max_r = max(max_r, p.rect.right)
            max_b = max(max_b, p.rect.bottom)
    return max_r, max_b


def _select_diverse(
    ordered: list[LayoutCandidate],
    top_k: int,
    min_diversity_threshold: float,
    *,
    buildable_width: float | None,
    buildable_depth: float | None,
) -> list[LayoutCandidate]:
    selected: list[LayoutCandidate] = []
    for candidate in ordered:
        if len(selected) >= top_k:
            break
        if any(
            layout_similarity(
                candidate,
                s,
                buildable_width=buildable_width,
                buildable_depth=buildable_depth,
            )
            >= min_diversity_threshold
            for s in selected
        ):
            continue
        selected.append(candidate)

    if len(selected) < top_k:
        selected_ids = {c.id for c in selected}
        for candidate in ordered:
            if len(selected) >= top_k:
                break
            if candidate.id not in selected_ids:
                selected.append(candidate)

    return selected


def rank_candidates(
    candidates: list[LayoutCandidate],
    top_k: int = 5,
    *,
    min_diversity_threshold: float | None = DEFAULT_MIN_DIVERSITY_THRESHOLD,
    buildable_width: float | None = None,
    buildable_depth: float | None = None,
    axis_alternatives: bool = True,
    mode: str | None = None,
) -> list[LayoutCandidate]:
    """Top-K 选择。

    ``mode``：
      - ``score``：纯总分
      - ``axis``：8.1 叙事轴 + 几何 diversity（**Alpha 默认**）
      - ``pareto``：8.2 非支配前沿（**opt-in**，非默认）

    兼容：``min_diversity_threshold=None`` → 纯分数；
    ``axis_alternatives=False`` 且未显式 mode → 仅几何 diversity。
    """
    valid = [
        c
        for c in candidates
        if c.validation and c.validation.valid and c.score is not None
    ]
    invalid = [c for c in candidates if c not in valid]

    valid.sort(key=lambda c: c.score or 0.0, reverse=True)
    invalid.sort(key=lambda c: c.score or 0.0, reverse=True)

    if min_diversity_threshold is None:
        resolved = "score"
    elif mode in ("score", "axis", "pareto"):
        resolved = mode
    elif not axis_alternatives:
        resolved = "geom"
    else:
        resolved = DEFAULT_RANK_MODE

    if resolved == "score" or not valid:
        selected = (valid + invalid)[:top_k]
        _stamp_selection(selected, resolved)
        return selected

    if resolved == "pareto":
        from solver.optimization.pareto import select_pareto_frontier

        selected = select_pareto_frontier(valid, top_k)
    elif resolved == "axis":
        from solver.optimization.diversity_select import select_diverse_alternatives

        selected = select_diverse_alternatives(
            valid,
            top_k,
            min_diversity_threshold=min_diversity_threshold or DEFAULT_MIN_DIVERSITY_THRESHOLD,
            buildable_width=buildable_width,
            buildable_depth=buildable_depth,
        )
    else:
        selected = _select_diverse(
            valid,
            top_k,
            min_diversity_threshold or DEFAULT_MIN_DIVERSITY_THRESHOLD,
            buildable_width=buildable_width,
            buildable_depth=buildable_depth,
        )

    if len(selected) < top_k:
        selected.extend(invalid[: top_k - len(selected)])
    _stamp_selection(selected, resolved)
    return selected


def _stamp_selection(candidates: list[LayoutCandidate], mode: str) -> None:
    """写入选优签名，便于 regression / 历史 Top-K 解释。"""
    sel_ver = selection_version_for(mode)
    for candidate in candidates:
        candidate.metrics["rank_mode"] = mode
        candidate.metrics["selection_version"] = sel_ver
        if candidate.provenance is not None:
            candidate.provenance = candidate.provenance.model_copy(
                update={"selection_version": sel_ver}
            )

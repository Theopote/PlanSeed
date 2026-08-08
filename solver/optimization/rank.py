"""候选排序 — score + 可选 diversity（LayoutSignature）。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from packages.schema.signature import build_layout_signature, signature_similarity

DEFAULT_MIN_DIVERSITY_THRESHOLD = 0.85


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
) -> list[LayoutCandidate]:
    """按 total_score 降序；无效 candidate 排末尾。"""
    valid = [
        c for c in candidates if c.validation and c.validation.valid and c.score is not None
    ]
    invalid = [c for c in candidates if c not in valid]

    valid.sort(key=lambda c: c.score or 0.0, reverse=True)
    invalid.sort(key=lambda c: c.score or 0.0, reverse=True)

    if min_diversity_threshold is not None and valid:
        selected = _select_diverse(
            valid,
            top_k,
            min_diversity_threshold,
            buildable_width=buildable_width,
            buildable_depth=buildable_depth,
        )
        if len(selected) < top_k:
            selected.extend(invalid[: top_k - len(selected)])
        return selected

    return (valid + invalid)[:top_k]

"""候选排序 — Phase 1 按 score；预留 diversity。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from solver.geometry.rect import from_placement


def layout_similarity(a: LayoutCandidate, b: LayoutCandidate) -> float:
    """
    两候选布局相似度 [0, 1]。

    TODO Phase 2+: 用于 diversity filtering，避免 Top 5 全是微调变体。
    """
    if len(a.floors) != len(b.floors):
        return 0.0

    diffs: list[float] = []
    for fa, fb in zip(a.floors, b.floors):
        map_a = {p.room_id: p for p in fa.placements if p.source.value == "program"}
        map_b = {p.room_id: p for p in fb.placements if p.source.value == "program"}
        for rid, pa in map_a.items():
            pb = map_b.get(rid)
            if pb is None:
                continue
            ra, rb = from_placement(pa.rect), from_placement(pb.rect)
            dx = abs(ra.x - rb.x) + abs(ra.y - rb.y)
            dw = abs(ra.width - rb.width) + abs(ra.depth - rb.depth)
            diffs.append(dx + dw)

    if not diffs:
        return 1.0
    avg_diff = sum(diffs) / len(diffs)
    return max(0.0, 1.0 - avg_diff / 5.0)


def rank_candidates(
    candidates: list[LayoutCandidate],
    top_k: int = 5,
    *,
    min_diversity_threshold: float | None = None,
) -> list[LayoutCandidate]:
    """
    按 total_score 降序；无效 candidate 排末尾。

    min_diversity_threshold: 预留参数，Phase 1 不启用 diversity filtering。
    """
    valid = [c for c in candidates if c.validation and c.validation.valid and c.score is not None]
    invalid = [c for c in candidates if c not in valid]

    valid.sort(key=lambda c: c.score or 0.0, reverse=True)
    invalid.sort(key=lambda c: c.score or 0.0, reverse=True)

    ranked = valid + invalid

    if min_diversity_threshold is not None and len(valid) > 1:
        # TODO: 实现 diversity-aware selection
        pass

    return ranked[:top_k]

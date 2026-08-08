"""候选排序 — score + 可选 diversity。"""

from __future__ import annotations

from packages.schema.layout import LayoutCandidate
from solver.geometry.rect import from_placement

# similarity ≥ 该阈值视为「过于相似」，diversity 筛选时跳过
DEFAULT_MIN_DIVERSITY_THRESHOLD = 0.85


def layout_similarity(a: LayoutCandidate, b: LayoutCandidate) -> float:
    """
    两候选布局相似度 [0, 1]。

    基于 program 房间矩形的位置与尺寸 L1 偏差。
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


def _select_diverse(
    ordered: list[LayoutCandidate],
    top_k: int,
    min_diversity_threshold: float,
) -> list[LayoutCandidate]:
    """贪心：按分数顺序选取，跳过与已选方案过于相似的候选。"""
    selected: list[LayoutCandidate] = []
    for candidate in ordered:
        if len(selected) >= top_k:
            break
        if any(
            layout_similarity(candidate, s) >= min_diversity_threshold for s in selected
        ):
            continue
        selected.append(candidate)

    # 若多样性过严导致不足 top_k，用剩余高分补齐
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
) -> list[LayoutCandidate]:
    """
    按 total_score 降序；无效 candidate 排末尾。

    min_diversity_threshold:
      - None：纯分数排序
      - float：贪心 diversity（默认 0.85）
    """
    valid = [
        c for c in candidates if c.validation and c.validation.valid and c.score is not None
    ]
    invalid = [c for c in candidates if c not in valid]

    valid.sort(key=lambda c: c.score or 0.0, reverse=True)
    invalid.sort(key=lambda c: c.score or 0.0, reverse=True)

    if min_diversity_threshold is not None and valid:
        selected = _select_diverse(valid, top_k, min_diversity_threshold)
        if len(selected) < top_k:
            selected.extend(invalid[: top_k - len(selected)])
        return selected

    return (valid + invalid)[:top_k]

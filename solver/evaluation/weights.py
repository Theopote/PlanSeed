"""评价权重 — 集中配置；与 Metric Ownership 对齐。"""

from pydantic import BaseModel, Field


class ScoreWeights(BaseModel):
    """
    Phase 3.5 分项权重（合计约 1.0；聚合时按实际和归一）。

    geometry 仅房间比例；program_fit 含面积份额；space_efficiency 仅紧凑度。
    """

    geometry: float = 0.12
    adjacency: float = 0.12
    vertical: float = 0.12
    site: float = 0.08
    orientation: float = 0.10
    circulation: float = 0.12
    privacy: float = 0.10
    program_fit: float = 0.12
    space_efficiency: float = 0.08
    layout_stability: float = 0.04

    aspect_ratio_threshold: float = 2.2
    min_adjacency_wall: float = 1.2


DEFAULT_WEIGHTS = ScoreWeights()

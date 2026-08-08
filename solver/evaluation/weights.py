"""评价权重 — 集中配置，避免 magic numbers。"""

from pydantic import BaseModel, Field


class ScoreWeights(BaseModel):
    """Phase 3：建筑评价分项权重（合计宜约 1.0；聚合时按实际和归一）。"""

    geometry: float = 0.20
    adjacency: float = 0.12
    vertical: float = 0.12
    site: float = 0.08
    orientation: float = 0.10
    circulation: float = 0.12
    privacy: float = 0.10
    program_fit: float = 0.08
    space_efficiency: float = 0.04
    layout_stability: float = 0.04

    aspect_ratio_threshold: float = 2.2
    min_adjacency_wall: float = 1.2


DEFAULT_WEIGHTS = ScoreWeights()

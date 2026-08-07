"""评价权重 — 集中配置，避免 magic numbers。"""

from pydantic import BaseModel, Field


class ScoreWeights(BaseModel):
    geometry: float = 0.35
    adjacency: float = 0.20
    vertical: float = 0.20
    site: float = 0.15
    circulation: float = 0.05
    orientation: float = 0.025
    privacy: float = 0.025

    aspect_ratio_threshold: float = 2.2
    min_adjacency_wall: float = 1.2


DEFAULT_WEIGHTS = ScoreWeights()

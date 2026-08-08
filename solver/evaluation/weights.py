"""评价权重 — 七轴（用户层）。"""

from pydantic import BaseModel


class ScoreWeights(BaseModel):
    """
    Program / Spatial / Circulation / Privacy / Environment / Technical / Robustness

    合计约 1.0；CompositeEvaluator 按实际和归一。
    """

    program: float = 0.18
    spatial: float = 0.14
    circulation: float = 0.16
    privacy: float = 0.12
    environment: float = 0.10
    technical: float = 0.16
    robustness: float = 0.14

    # 子合成（轴内，不进入 total 二次加权之外）
    program_fit_share: float = 0.65  # vs adjacency
    spatial_proportion_share: float = 0.55  # vs compactness
    technical_vertical_share: float = 0.55  # vs site

    aspect_ratio_threshold: float = 2.2
    min_adjacency_wall: float = 1.2


DEFAULT_WEIGHTS = ScoreWeights()

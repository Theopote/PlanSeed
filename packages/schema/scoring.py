"""评价结果模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schema.layout import Violation


class DesignMetrics(BaseModel):
    """第一阶段 metrics — 可扩展。"""

    overlap_count: int = 0
    boundary_violation: int = 0
    area_error: float = 0.0
    min_width_violation: int = 0
    aspect_ratio_penalty: float = 0.0
    compactness: float = 0.0

    required_adjacency_satisfaction: float = 0.0
    preferred_adjacency_satisfaction: float = 0.0

    stair_alignment: float = 0.0
    wet_zone_alignment: float = 0.0

    setback_compliance: float = 1.0
    orientation_satisfaction: float = 1.0


class DesignScore(BaseModel):
    geometry_score: float = 0.0
    adjacency_score: float = 0.0
    circulation_score: float = 0.0
    orientation_score: float = 0.0
    privacy_score: float = 0.0
    vertical_score: float = 0.0
    site_score: float = 0.0

    total_score: float = 0.0

    metrics: DesignMetrics = Field(default_factory=DesignMetrics)
    warnings: list[str] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)

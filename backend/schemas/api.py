"""FastAPI 请求/响应模型（≠ solver 领域模型）。"""

from __future__ import annotations

from typing import Any

from packages.schema.requirements import RequirementSpec
from packages.schema.scoring import DesignScore
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """生成请求：基准案例或 RequirementSpec。"""

    use_benchmark: bool = False
    requirements: RequirementSpec | None = None
    candidate_count: int | None = Field(default=None, ge=1, le=64)
    return_top_k: int | None = Field(default=None, ge=1, le=16)


class RoomSummary(BaseModel):
    id: str
    name: str
    category: str
    target_area: float
    floor_id: str | None = None


class ProgramSummary(BaseModel):
    project_id: str
    site_width: float
    site_depth: float
    floor_count: int
    rooms: list[RoomSummary]
    floors: list[dict[str, Any]]
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)


class CandidatePayload(BaseModel):
    id: str
    seed: int
    score: float | None
    label: str
    svg: str
    design_score: DesignScore | None = None
    validation: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    generated: int
    valid: int
    rejected: int
    program_summary: ProgramSummary
    candidates: list[CandidatePayload]

"""HTTP API 请求/响应模型。"""

from backend.schemas.api import (
    CandidatePayload,
    GenerateRequest,
    GenerateResponse,
    ProgramSummary,
    RejectedCandidatePayload,
    RoomSummary,
)

__all__ = [
    "CandidatePayload",
    "GenerateRequest",
    "GenerateResponse",
    "ProgramSummary",
    "RejectedCandidatePayload",
    "RoomSummary",
]

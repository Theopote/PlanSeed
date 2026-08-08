"""HTTP API 请求/响应模型。"""

from backend.schemas.api import (
    CandidatePayload,
    CandidateProvenance,
    CompareRequest,
    CompareResponse,
    GenerateRequest,
    GenerateResponse,
    ProgramSummary,
    RejectedCandidatePayload,
    RoomSummary,
)

__all__ = [
    "CandidatePayload",
    "CandidateProvenance",
    "CompareRequest",
    "CompareResponse",
    "GenerateRequest",
    "GenerateResponse",
    "ProgramSummary",
    "RejectedCandidatePayload",
    "RoomSummary",
]

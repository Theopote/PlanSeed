"""需求相关路由 — Phase 6.5 NL parse。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from packages.llm import LLMIngestError, LLMRepairExhaustedError
from packages.llm.ollama import OllamaConnectionError, OllamaHTTPError
from packages.schema.requirements import RequirementSpec
from pydantic import BaseModel, Field, field_validator

from backend.services.nl_parse import parse_nl_requirement

router = APIRouter(tags=["requirements"])


class ParseNLRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    max_repairs: int = Field(default=2, ge=0, le=5)

    @field_validator("text")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("需求文本为空")
        return s



class ParseNLResponse(BaseModel):
    requirement_spec: RequirementSpec
    attempts: int
    repair_notes: list[str] = Field(default_factory=list)
    provider: str
    raw: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/requirements/parse", response_model=ParseNLResponse)
def parse_requirements_nl(body: ParseNLRequest) -> ParseNLResponse:
    """自然语言 → RequirementSpec（含有限 repair；无几何）。"""
    try:
        out = parse_nl_requirement(body.text, max_repairs=body.max_repairs)
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaHTTPError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMRepairExhaustedError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "errors": exc.errors,
                "attempts": exc.attempts,
            },
        ) from exc
    except LLMIngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ParseNLResponse(
        requirement_spec=out.spec,
        attempts=out.attempts,
        repair_notes=list(out.repair_notes),
        provider=out.provider,
        raw=out.raw,
    )

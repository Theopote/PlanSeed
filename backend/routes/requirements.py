"""需求相关路由 — Phase 6.5 NL parse。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from packages.llm import LLMIngestError, LLMRepairExhaustedError
from packages.llm.health import LlmHealthState, probe_llm_health
from packages.llm.ollama import OllamaConnectionError, OllamaHTTPError, OllamaProvider
from packages.schema.limits import API_LIMITS
from packages.schema.requirements import RequirementSpec
from pydantic import BaseModel, Field, field_validator

from backend.services.nl_parse import get_nl_provider, parse_nl_requirement

router = APIRouter(tags=["requirements"])


def _preflight_llm_or_raise() -> None:
    """解析前检查模型是否已安装；避免点「解析需求」后才撞 model not found。"""
    prov = get_nl_provider()
    if not isinstance(prov, OllamaProvider):
        return  # mock / 测试注入：不探测本机 Ollama
    status = probe_llm_health(provider=prov)
    if status.state == LlmHealthState.LLM_UNAVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=status.detail or "无法连接 Ollama",
        )
    if status.state == LlmHealthState.MODEL_MISSING:
        raise HTTPException(
            status_code=503,
            detail=status.detail or f"未检测到 {status.model}",
        )


class ParseNLRequest(BaseModel):
    text: str = Field(min_length=1, max_length=API_LIMITS.max_nl_text_chars)
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
    _preflight_llm_or_raise()
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

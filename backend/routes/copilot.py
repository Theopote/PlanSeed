"""AI Design Copilot API — IntentPatch / Strategy / Critic / Optimize / Conversation。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from packages.llm.intent_parser import parse_intent_patch
from packages.schema.design_conversation import (
    ConversationMessage,
    ConversationRole,
    DesignConversationState,
)
from packages.schema.intent_patch import DesignIntentPatch, IntentPatchPreview
from packages.schema.layout import LayoutCandidate
from packages.schema.topology_strategy import BUILTIN_STRATEGIES, TopologyStrategy
from pydantic import BaseModel, Field
from solver.critique.critic import critique_candidate
from solver.intent.apply import apply_intent_patch
from solver.topology.strategy import apply_topology_strategy, list_builtin_strategies

from backend.schemas.api import GenerateRequest
from backend.services.generation import resolve_solve_input
from backend.services.serialization import serialize_candidate

router = APIRouter(tags=["copilot"])


class IntentParseRequest(BaseModel):
    text: str = Field(min_length=1)
    target_candidate: str = "selected"
    requirements: GenerateRequest | None = None
    use_benchmark: bool = False
    candidate: dict | None = None


class IntentPreviewRequest(BaseModel):
    patch: DesignIntentPatch
    use_benchmark: bool = True


class IntentPreviewResponse(BaseModel):
    preview: IntentPatchPreview
    patch: DesignIntentPatch
    locked_rooms: list[str] = Field(default_factory=list)
    mutable_rooms: list[str] = Field(default_factory=list)


class CritiqueRequest(BaseModel):
    use_benchmark: bool = True
    candidate: dict = Field(description="LayoutCandidate 子集 JSON")


class OptimizeRequest(BaseModel):
    use_benchmark: bool = True
    candidate: dict
    max_rounds: int = Field(default=2, ge=1, le=5)
    candidate_budget: int = Field(default=4, ge=2, le=16)


class ConversationUpsertRequest(BaseModel):
    project_id: str
    state: DesignConversationState


class ConversationAppendRequest(BaseModel):
    project_id: str
    role: ConversationRole
    content: str
    meta: dict = Field(default_factory=dict)


@router.get("/api/copilot/strategies", response_model=list[TopologyStrategy])
def list_strategies() -> list[TopologyStrategy]:
    return list_builtin_strategies()


@router.post("/api/copilot/intent/parse", response_model=DesignIntentPatch)
def parse_intent(body: IntentParseRequest) -> DesignIntentPatch:
    return parse_intent_patch(body.text, target_candidate=body.target_candidate)


@router.post("/api/copilot/intent/preview", response_model=IntentPreviewResponse)
def preview_intent(body: IntentPreviewRequest) -> IntentPreviewResponse:
    from backend.schemas.api import GenerateRequest as GR

    program = resolve_solve_input(GR(use_benchmark=body.use_benchmark)).program
    _prog, scope, preview = apply_intent_patch(program, body.patch)
    return IntentPreviewResponse(
        preview=preview,
        patch=body.patch,
        locked_rooms=list(scope.locked_rooms),
        mutable_rooms=list(scope.mutable_rooms),
    )


@router.post("/api/copilot/critique")
def critique(body: CritiqueRequest) -> dict:
    from backend.schemas.api import GenerateRequest as GR

    program = resolve_solve_input(GR(use_benchmark=body.use_benchmark)).program
    try:
        cand = LayoutCandidate.model_validate(body.candidate)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"candidate 无效：{exc}") from exc
    return critique_candidate(program, cand)


@router.post("/api/copilot/optimize")
def optimize(body: OptimizeRequest) -> dict:
    from solver.optimization.session import run_optimization_session

    from backend.schemas.api import GenerateRequest as GR

    program = resolve_solve_input(GR(use_benchmark=body.use_benchmark)).program
    try:
        cand = LayoutCandidate.model_validate(body.candidate)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"candidate 无效：{exc}") from exc
    result = run_optimization_session(
        program,
        cand,
        max_rounds=body.max_rounds,
        candidate_budget=body.candidate_budget,
    )
    best = None
    if result.best is not None:
        best = serialize_candidate(result.program, result.best, 0)
    return {
        "stopped_reason": result.stopped_reason,
        "rounds": [
            {
                "index": r.index,
                "candidate_id": r.candidate_id,
                "score": r.score,
                "private_through": r.private_through,
                "gate_pass": r.gate_pass,
                "stopped_reason": r.stopped_reason,
                "patch": r.patch.model_dump() if r.patch else None,
            }
            for r in result.rounds
        ],
        "best": best,
    }


@router.post("/api/copilot/strategy/apply")
def apply_strategy(body: dict) -> dict:
    """将内置策略合并进 benchmark/requirements program，返回摘要。"""
    from backend.schemas.api import GenerateRequest as GR

    strategy_id = str(body.get("strategy_id") or "")
    use_benchmark = bool(body.get("use_benchmark", True))
    program = resolve_solve_input(GR(use_benchmark=use_benchmark)).program
    try:
        program2 = apply_topology_strategy(program, strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "strategy_id": strategy_id,
        "room_graph_edges": len(program2.room_graph.edges) if program2.room_graph else 0,
        "room_count": len(program2.rooms),
    }


# 进程内会话（桌面单用户）；项目 payload 同步由客户端负责持久化
_CONVERSATIONS: dict[str, DesignConversationState] = {}


@router.get("/api/copilot/conversation/{project_id}")
def get_conversation(project_id: str) -> DesignConversationState:
    if project_id not in _CONVERSATIONS:
        _CONVERSATIONS[project_id] = DesignConversationState(project_id=project_id)
    return _CONVERSATIONS[project_id]


@router.put("/api/copilot/conversation/{project_id}")
def put_conversation(
    project_id: str, body: DesignConversationState
) -> DesignConversationState:
    state = body.model_copy(update={"project_id": project_id})
    _CONVERSATIONS[project_id] = state
    return state


@router.post("/api/copilot/conversation/{project_id}/messages")
def append_message(
    project_id: str, body: ConversationAppendRequest
) -> DesignConversationState:
    from uuid import uuid4

    state = _CONVERSATIONS.get(project_id) or DesignConversationState(
        project_id=project_id
    )
    msg = ConversationMessage(
        id=str(uuid4()),
        role=body.role,
        content=body.content,
        meta=body.meta,
    )
    messages = list(state.messages) + [msg]
    state = state.model_copy(update={"messages": messages})
    _CONVERSATIONS[project_id] = state
    return state


@router.get("/api/copilot/builtins")
def builtins_meta() -> dict:
    return {
        "strategies": [s.model_dump() for s in BUILTIN_STRATEGIES],
        "intent_actions": [
            "increase_target_area",
            "decrease_target_area",
            "set_orientation_preference",
            "avoid_private_through",
            "require_adjacency",
            "avoid_adjacency",
            "reduce_corridor_preference",
        ],
    }

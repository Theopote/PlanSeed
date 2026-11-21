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
from packages.schema.locks import LayoutLocks
from packages.schema.topology_strategy import BUILTIN_STRATEGIES, TopologyStrategy
from pydantic import BaseModel, Field
from solver.critique.critic import critique_candidate
from solver.intent.apply import apply_intent_patch
from solver.intent.spec_sync import sync_requirement_spec_after_intent
from solver.topology.strategy import apply_topology_strategy, list_builtin_strategies

from backend.schemas.api import GenerateRequest, GenerateResponse, RoomPlacementPayload
from backend.services.candidate_rebuild import (
    CandidateRebuildError,
    layout_candidate_from_copilot_payload,
)
from backend.services.generation import (
    generate_layouts,
    placements_to_locked_rects,
    resolve_solve_input,
)
from backend.services.serialization import (
    serialize_candidate,
    serialize_program_summary,
    serialize_rejected,
)

router = APIRouter(tags=["copilot"])

MAX_REJECTED_SAMPLES = 8


class IntentParseRequest(BaseModel):
    text: str = Field(min_length=1)
    target_candidate: str = "selected"
    use_benchmark: bool = False


class IntentPreviewRequest(BaseModel):
    patch: DesignIntentPatch
    use_benchmark: bool = True
    requirements: object | None = None


class IntentPreviewResponse(BaseModel):
    preview: IntentPatchPreview
    patch: DesignIntentPatch
    locked_rooms: list[str] = Field(default_factory=list)
    mutable_rooms: list[str] = Field(default_factory=list)


class IntentApplyRequest(BaseModel):
    patch: DesignIntentPatch
    use_benchmark: bool = False
    requirements: object | None = None
    base_placements: list[RoomPlacementPayload] = Field(min_length=1)
    locks: LayoutLocks | None = None
    candidate_count: int = Field(default=8, ge=2, le=32)
    return_top_k: int = Field(default=3, ge=1, le=10)
    base_seed: int = Field(default=0, ge=0)


class CritiqueRequest(BaseModel):
    use_benchmark: bool = True
    requirements: object | None = None
    candidate: dict = Field(description="LayoutCandidate 子集 JSON")


class OptimizeRequest(BaseModel):
    use_benchmark: bool = True
    requirements: object | None = None
    candidate: dict
    locks: LayoutLocks | None = None
    max_rounds: int = Field(default=2, ge=1, le=5)
    candidate_budget: int = Field(default=4, ge=2, le=16)


class StrategyGenerateRequest(BaseModel):
    strategy_id: str
    use_benchmark: bool = False
    requirements: object | None = None
    candidate_count: int = Field(default=12, ge=2, le=32)
    return_top_k: int = Field(default=5, ge=1, le=10)
    base_seed: int = Field(default=0, ge=0)


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


def _solve_request(
    *,
    use_benchmark: bool,
    requirements: object | None,
    candidate_count: int | None = None,
    return_top_k: int | None = None,
    base_seed: int | None = None,
) -> GenerateRequest:
    from packages.schema.requirements import RequirementSpec

    reqs = None
    if requirements is not None:
        reqs = (
            requirements
            if isinstance(requirements, RequirementSpec)
            else RequirementSpec.model_validate(requirements)
        )
    return GenerateRequest(
        use_benchmark=use_benchmark,
        requirements=reqs,
        candidate_count=candidate_count,
        return_top_k=return_top_k,
        base_seed=base_seed,
    )


def _generate_response(
    program,
    result,
    *,
    top=None,
    requirement_spec=None,
) -> GenerateResponse:
    from packages.schema.identity import solver_identity

    selected = list(top if top is not None else result.top_candidates)
    candidates = [
        serialize_candidate(
            program, cand, i, requirement_spec=requirement_spec
        )
        for i, cand in enumerate(selected)
    ]
    invalid = [
        c
        for c in result.all_candidates
        if c.validation is not None and not c.validation.valid
    ]
    invalid.sort(key=lambda c: c.seed)
    return GenerateResponse(
        generated=result.generated,
        valid=result.valid,
        rejected=result.rejected,
        program_summary=serialize_program_summary(program),
        requirement_spec=requirement_spec,
        candidates=candidates,
        violation_summary=dict(result.violation_summary),
        rejected_candidates=[
            serialize_rejected(c) for c in invalid[:MAX_REJECTED_SAMPLES]
        ],
        solver_identity=solver_identity(),
    )


@router.post("/api/copilot/intent/preview", response_model=IntentPreviewResponse)
def preview_intent(body: IntentPreviewRequest) -> IntentPreviewResponse:
    program = resolve_solve_input(
        _solve_request(use_benchmark=body.use_benchmark, requirements=body.requirements)
    ).program
    _prog, _scope, preview = apply_intent_patch(program, body.patch)
    # 顶层字段须反映实际锁定集合（preview.locked_rooms），非 scope 空列表
    return IntentPreviewResponse(
        preview=preview,
        patch=body.patch,
        locked_rooms=list(preview.locked_rooms),
        mutable_rooms=list(preview.mutable_rooms),
    )


@router.post("/api/copilot/intent/apply", response_model=GenerateResponse)
def apply_intent(body: IntentApplyRequest) -> GenerateResponse:
    """应用 IntentPatch → 局部重生成（保留 preserve 锁定）。"""
    from solver.regeneration.errors import RegenerationScopeError
    from solver.regeneration.scope import (
        filter_candidates_preserving_topology,
        locks_from_placement_rects,
        merge_layout_locks,
    )

    resolved = resolve_solve_input(
        _solve_request(
            use_benchmark=body.use_benchmark,
            requirements=body.requirements,
            candidate_count=body.candidate_count,
            return_top_k=body.return_top_k,
            base_seed=body.base_seed,
        )
    )
    program = resolved.program
    try:
        patched, scope, preview = apply_intent_patch(program, body.patch)
        if not preview.ok and not preview.program_deltas:
            raise HTTPException(status_code=422, detail="意图补丁无可执行变更")
        # RequirementSpec 是唯一需求事实源：补丁必须写回，不能只改一次性 Program
        requirement_spec = resolved.requirement_spec
        if requirement_spec is not None:
            requirement_spec = sync_requirement_spec_after_intent(
                requirement_spec, patched, body.patch
            )
        rects = placements_to_locked_rects(body.base_placements)
        scope_locks = locks_from_placement_rects(scope, patched, rects)
        locks = merge_layout_locks(
            body.locks, scope_locks, mutable_room_ids=scope.mutable_room_ids
        )
        result = generate_layouts(patched, locks=locks)
        top = filter_candidates_preserving_topology(
            scope, patched, list(result.top_candidates)
        )
    except RegenerationScopeError as exc:
        raise HTTPException(status_code=422, detail=exc.to_detail()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _generate_response(
        patched, result, top=top, requirement_spec=requirement_spec
    )


def _require_layout_candidate(raw: dict) -> LayoutCandidate:
    try:
        return layout_candidate_from_copilot_payload(raw)
    except CandidateRebuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/copilot/critique")
def critique(body: CritiqueRequest) -> dict:
    program = resolve_solve_input(
        _solve_request(use_benchmark=body.use_benchmark, requirements=body.requirements)
    ).program
    cand = _require_layout_candidate(body.candidate)
    return critique_candidate(program, cand)


@router.post("/api/copilot/optimize")
def optimize(body: OptimizeRequest) -> dict:
    from solver.optimization.session import run_optimization_session

    program = resolve_solve_input(
        _solve_request(use_benchmark=body.use_benchmark, requirements=body.requirements)
    ).program
    cand = _require_layout_candidate(body.candidate)
    result = run_optimization_session(
        program,
        cand,
        max_rounds=body.max_rounds,
        candidate_budget=body.candidate_budget,
        user_locks=body.locks,
    )
    # 仅当会话选出相对输入候选的新几何时回传 best，避免前端重复追加
    improved = result.best is not None and result.best.id != cand.id
    best = None
    if improved and result.best is not None:
        best = serialize_candidate(
            result.program,
            result.best,
            0,
            requirement_spec=body.requirements,
        )
    return {
        "stopped_reason": result.stopped_reason,
        "improved": improved,
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
    """将内置策略合并进 program，返回摘要。"""
    strategy_id = str(body.get("strategy_id") or "")
    use_benchmark = bool(body.get("use_benchmark", True))
    program = resolve_solve_input(
        _solve_request(
            use_benchmark=use_benchmark, requirements=body.get("requirements")
        )
    ).program
    try:
        program2 = apply_topology_strategy(program, strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "strategy_id": strategy_id,
        "room_graph_edges": len(program2.room_graph.edges) if program2.room_graph else 0,
        "room_count": len(program2.rooms),
    }


@router.post("/api/copilot/strategy/generate", response_model=GenerateResponse)
def generate_with_strategy(body: StrategyGenerateRequest) -> GenerateResponse:
    """按命名策略物化 RoomGraph 后整栋生成，候选带 strategy 标签。"""
    from packages.schema.topology_strategy import builtin_strategy
    from solver.topology.strategy import tag_candidates_with_strategy

    strategy = builtin_strategy(body.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"未知策略：{body.strategy_id}")
    resolved = resolve_solve_input(
        _solve_request(
            use_benchmark=body.use_benchmark,
            requirements=body.requirements,
            candidate_count=body.candidate_count,
            return_top_k=body.return_top_k,
            base_seed=body.base_seed,
        )
    )
    program = apply_topology_strategy(resolved.program, strategy)
    result = generate_layouts(program)
    tag_candidates_with_strategy(result.top_candidates, strategy)
    tag_candidates_with_strategy(result.all_candidates, strategy)
    return _generate_response(
        program, result, requirement_spec=resolved.requirement_spec
    )


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

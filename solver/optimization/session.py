"""OptimizationSession — 受控多轮补丁 + 局部 regen。"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.schema.intent_patch import DesignIntentPatch
from packages.schema.layout import LayoutCandidate
from packages.schema.locks import LayoutLocks
from packages.schema.program import DesignProgram
from packages.schema.regeneration import RegenerationScope
from solver.critique.critic import critique_candidate
from solver.intent.apply import apply_intent_patch
from solver.regeneration.errors import RegenerationScopeError
from solver.regeneration.scope import (
    filter_candidates_preserving_topology,
    locks_from_regeneration_scope,
    merge_layout_locks,
)


@dataclass
class OptimizationRound:
    index: int
    patch: DesignIntentPatch | None
    candidate_id: str | None
    score: float | None
    private_through: int
    gate_pass: bool
    stopped_reason: str | None = None


@dataclass
class OptimizationSessionResult:
    program: DesignProgram
    best: LayoutCandidate | None
    rounds: list[OptimizationRound] = field(default_factory=list)
    stopped_reason: str = "completed"


def _score_of(c: LayoutCandidate) -> float:
    if c.score is not None:
        return float(c.score)
    if c.evaluation is not None:
        return float(c.evaluation.total_score)
    return float(c.metrics.get("total_score") or 0.0)


def _priv(c: LayoutCandidate) -> int:
    return int(c.metrics.get("private_through_count") or 0)


def _gate_ok(c: LayoutCandidate) -> bool:
    return bool(c.metrics.get("architectural_gate_pass", True))


def candidate_quality_key(c: LayoutCandidate) -> tuple[int, int, float]:
    """Gate 优先 → 更少穿卧室 → 更高分（越小越好）。"""
    return (
        0 if _gate_ok(c) else 1,
        _priv(c),
        -_score_of(c),
    )


def _respect_user_locks(
    scope: RegenerationScope,
    user_locks: LayoutLocks | None,
) -> RegenerationScope:
    """用户显式锁定优先：从 mutable 中剔除，冲突无解时抛错。"""
    if user_locks is None or not user_locks.rooms:
        return scope
    locked = {r.room_id for r in user_locks.rooms}
    mutable = [m for m in scope.mutable_rooms if m not in locked]
    if not mutable:
        raise RegenerationScopeError(
            "用户锁定与优化可变范围冲突：无可移动房间",
            code="user_lock_blocks_optimization",
            room_ids=sorted(locked),
        )
    return scope.model_copy(update={"mutable_rooms": mutable})


def run_optimization_session(
    program: DesignProgram,
    base_candidate: LayoutCandidate,
    *,
    max_rounds: int = 3,
    candidate_budget: int = 8,
    user_locks: LayoutLocks | None = None,
    generate_fn=None,
) -> OptimizationSessionResult:
    """
    读取 Critic → 应用建议补丁 → 局部 regen → 比较；受停止条件约束。

    ``generate_fn(program, locks) -> list[LayoutCandidate]`` 可注入；
    默认调用 Guillotine + 简单评价管线。
    用户 ``user_locks`` 优先于 Intent 推导的 mutable。
    """
    if generate_fn is None:

        def generate_fn(prog, locks):  # type: ignore[no-redef]
            from solver.generators.guillotine import GuillotineGenerator
            from solver.pipeline import run_pipeline

            cfg = prog.solver_config.model_copy(
                update={
                    "candidate_count": max(2, candidate_budget),
                    "return_top_k": min(3, max(1, candidate_budget)),
                }
            )
            prog = prog.model_copy(update={"solver_config": cfg})
            result = run_pipeline(prog, locks=locks, generator=GuillotineGenerator())
            return list(result.top_candidates)

    current_program = program
    best = base_candidate
    rounds: list[OptimizationRound] = []
    no_improve = 0
    stopped = "completed"

    for i in range(max_rounds):
        critique = critique_candidate(current_program, best)
        patches = critique.get("suggested_patches") or []
        if not patches:
            stopped = "no_suggested_patches"
            rounds.append(
                OptimizationRound(
                    index=i,
                    patch=None,
                    candidate_id=best.id,
                    score=_score_of(best),
                    private_through=_priv(best),
                    gate_pass=_gate_ok(best),
                    stopped_reason=stopped,
                )
            )
            break

        patch = DesignIntentPatch.model_validate(patches[0])
        new_program, scope, preview = apply_intent_patch(
            current_program, patch, candidate=best
        )
        if not preview.ok and not preview.program_deltas:
            stopped = "patch_not_applicable"
            rounds.append(
                OptimizationRound(
                    index=i,
                    patch=patch,
                    candidate_id=best.id,
                    score=_score_of(best),
                    private_through=_priv(best),
                    gate_pass=_gate_ok(best),
                    stopped_reason=stopped,
                )
            )
            break

        try:
            scope = _respect_user_locks(scope, user_locks)
            scope_locks = locks_from_regeneration_scope(scope, new_program, best)
            locks = merge_layout_locks(
                user_locks,
                scope_locks,
                mutable_room_ids=set(scope.mutable_rooms),
            )
            cands = generate_fn(new_program, locks)
            cands = filter_candidates_preserving_topology(scope, new_program, cands)
        except RegenerationScopeError as exc:
            stopped = f"lock_conflict:{exc.code}"
            rounds.append(
                OptimizationRound(
                    index=i,
                    patch=patch,
                    candidate_id=best.id,
                    score=_score_of(best),
                    private_through=_priv(best),
                    gate_pass=_gate_ok(best),
                    stopped_reason=stopped,
                )
            )
            break
        except Exception as exc:  # noqa: BLE001
            stopped = f"regen_failed:{type(exc).__name__}"
            rounds.append(
                OptimizationRound(
                    index=i,
                    patch=patch,
                    candidate_id=best.id,
                    score=_score_of(best),
                    private_through=_priv(best),
                    gate_pass=_gate_ok(best),
                    stopped_reason=stopped,
                )
            )
            break

        if not cands:
            stopped = "empty_candidates"
            break

        # 优先 Gate → 更少 private_through → 更高分（与 improved 同序）
        ranked = sorted(cands, key=candidate_quality_key)
        nxt = ranked[0]
        improved = candidate_quality_key(nxt) < candidate_quality_key(best)
        rounds.append(
            OptimizationRound(
                index=i,
                patch=patch,
                candidate_id=nxt.id,
                score=_score_of(nxt),
                private_through=_priv(nxt),
                gate_pass=_gate_ok(nxt),
            )
        )
        if improved:
            best = nxt
            current_program = new_program
            best.variant_parent_id = base_candidate.id
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= 2:
                stopped = "no_improvement_x2"
                rounds[-1].stopped_reason = stopped
                break
    else:
        stopped = "max_rounds"

    return OptimizationSessionResult(
        program=current_program,
        best=best,
        rounds=rounds,
        stopped_reason=stopped,
    )

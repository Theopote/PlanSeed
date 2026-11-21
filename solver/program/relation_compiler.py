"""RequirementSpec.relation_intents → DesignProgram 约束 / AccessGraph。"""

from __future__ import annotations

from uuid import uuid4

from packages.schema.constraints import (
    AdjacencyConstraint,
    ConstraintSource,
    SeparationConstraint,
)
from packages.schema.program import DesignProgram
from packages.schema.requirements import RequirementSpec
from packages.schema.topology import AccessGraph, SpaceConnection, SpaceConnectionType


def _resolve_token(program: DesignProgram, token: str) -> list[str]:
    """按 id 优先、再按名称解析；同名多命中时全部返回（调用方决定）。"""
    key = (token or "").strip()
    if not key:
        return []
    by_id = [r.id for r in program.rooms if r.id == key]
    if by_id:
        return by_id
    return [r.id for r in program.rooms if (r.name or "") == key]


def _pick_pair(
    program: DesignProgram, a: str, b: str
) -> tuple[str, str] | None:
    """一对一解析；任一侧无命中或多歧义则跳过（避免错绑）。"""
    ra = _resolve_token(program, a)
    rb = _resolve_token(program, b)
    if len(ra) != 1 or len(rb) != 1:
        return None
    if ra[0] == rb[0]:
        return None
    return ra[0], rb[0]


def compile_relation_intents(
    req: RequirementSpec,
    program: DesignProgram,
) -> DesignProgram:
    """
    将 relation_intents 编译进 constraints 与 access_graph。

    - adjacency / near → AdjacencyConstraint（near 为软、不强制共墙）
    - separation → SeparationConstraint
    - access → SpaceConnection(DOOR)
    - open_connection → SpaceConnection(OPEN)
    - visual_connection → 暂跳过（预留）
    """
    constraints = list(program.constraints)
    access = program.access_graph or AccessGraph(
        node_ids=[r.id for r in program.rooms]
    )
    # 保证节点齐全
    for r in program.rooms:
        if r.id not in access.node_ids:
            access.node_ids.append(r.id)

    for intent in req.relation_intents:
        pair = _pick_pair(program, intent.a, intent.b)
        if pair is None:
            continue
        a_id, b_id = pair
        hard = intent.strength == "required"
        weight = 1.0 if hard else 0.7
        sk = f"relation_intents.{intent.kind}"
        note = intent.note or f"{intent.a}↔{intent.b}"

        if intent.kind in ("adjacency", "near"):
            constraints.append(
                AdjacencyConstraint(
                    id=f"rel-adj-{uuid4().hex[:8]}",
                    room_a_id=a_id,
                    room_b_id=b_id,
                    share_wall=intent.kind == "adjacency",
                    hard=hard and intent.kind == "adjacency",
                    weight=weight,
                    source=ConstraintSource.NORMALIZER,
                    source_key=sk,
                    description=f"RelationIntent {intent.kind}: {note}",
                )
            )
        elif intent.kind == "separation":
            constraints.append(
                SeparationConstraint(
                    id=f"rel-sep-{uuid4().hex[:8]}",
                    room_a_id=a_id,
                    room_b_id=b_id,
                    hard=hard,
                    weight=weight,
                    source=ConstraintSource.NORMALIZER,
                    source_key=sk,
                    description=f"RelationIntent separation: {note}",
                )
            )
        elif intent.kind in ("access", "open_connection"):
            ctype = (
                SpaceConnectionType.DOOR
                if intent.kind == "access"
                else SpaceConnectionType.OPEN
            )
            access.add_connection(
                SpaceConnection(
                    id=f"rel-acc-{uuid4().hex[:8]}",
                    a=a_id,
                    b=b_id,
                    type=ctype,
                    required=hard,
                    weight=weight,
                    description=f"RelationIntent {intent.kind}: {note}",
                )
            )
        # visual_connection: 预留

    return program.model_copy(
        update={"constraints": constraints, "access_graph": access}
    )

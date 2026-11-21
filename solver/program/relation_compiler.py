"""RequirementSpec.relation_intents → DesignProgram 约束 / AccessGraph / RoomGraph。"""

from __future__ import annotations

from packages.schema.constraints import (
    AdjacencyConstraint,
    ConstraintSource,
    SeparationConstraint,
)
from packages.schema.program import DesignProgram
from packages.schema.project import ProjectSpec
from packages.schema.requirements import RequirementSpec
from packages.schema.topology import (
    AccessGraph,
    RoomGraph,
    SpaceConnection,
    SpaceConnectionType,
)
from solver.program.normalize import build_room_graph


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


def _stable_pair_id(prefix: str, a: str, b: str) -> str:
    x, y = (a, b) if a <= b else (b, a)
    return f"{prefix}-{x}-{y}"


def _rebuild_room_graph(program: DesignProgram) -> RoomGraph:
    """按当前 constraints（含 relation 编译结果）重建 RoomGraph。"""
    pseudo = ProjectSpec(
        id=program.project_id or "from-program",
        site=program.site,
        floors=program.floors,
        rooms=program.rooms,
        constraints=program.constraints,
    )
    return build_room_graph(pseudo)


def compile_relation_intents(
    req: RequirementSpec,
    program: DesignProgram,
) -> DesignProgram:
    """
    将 relation_intents 编译进 constraints / access_graph / room_graph。

    - adjacency → AdjacencyConstraint(share_wall=True) + RoomEdge ADJACENT
    - near → AdjacencyConstraint(share_wall=False, soft) + RoomEdge NEAR
    - separation → SeparationConstraint + RoomEdge AVOID
    - access → SpaceConnection(DOOR)
    - open_connection → SpaceConnection(OPEN)
    - visual_connection → 暂跳过（预留）

    注意：无 access 类意图时**不**创建空 AccessGraph，以免占位挡住
    ``ensure_access_graph`` 的住宅默认通行图派生。
    """
    constraints = list(program.constraints)
    # 仅在真正写入通行边时才物化 AccessGraph
    access: AccessGraph | None = program.access_graph
    existing_ids = {c.id for c in constraints}
    if access is not None:
        existing_ids.update(c.id for c in access.connections)

    for intent in req.relation_intents:
        pair = _pick_pair(program, intent.a, intent.b)
        if pair is None:
            continue
        a_id, b_id = pair
        hard = intent.strength == "required"
        weight = 1.0 if hard else 0.7
        sk = f"relation_intents.{intent.kind}"
        note = intent.note or f"{intent.a}↔{intent.b}"

        if intent.kind == "adjacency":
            cid = _stable_pair_id("rel-adj", a_id, b_id)
            if cid in existing_ids:
                continue
            constraints.append(
                AdjacencyConstraint(
                    id=cid,
                    room_a_id=a_id,
                    room_b_id=b_id,
                    share_wall=True,
                    hard=hard,
                    weight=weight,
                    source=ConstraintSource.NORMALIZER,
                    source_key=sk,
                    description=f"RelationIntent adjacency: {note}",
                )
            )
            existing_ids.add(cid)
        elif intent.kind == "near":
            cid = _stable_pair_id("rel-near", a_id, b_id)
            if cid in existing_ids:
                continue
            constraints.append(
                AdjacencyConstraint(
                    id=cid,
                    room_a_id=a_id,
                    room_b_id=b_id,
                    share_wall=False,
                    hard=False,
                    weight=weight,
                    source=ConstraintSource.NORMALIZER,
                    source_key=sk,
                    description=f"RelationIntent near: {note}",
                )
            )
            existing_ids.add(cid)
        elif intent.kind == "separation":
            cid = _stable_pair_id("rel-sep", a_id, b_id)
            if cid in existing_ids:
                continue
            constraints.append(
                SeparationConstraint(
                    id=cid,
                    room_a_id=a_id,
                    room_b_id=b_id,
                    hard=hard,
                    weight=weight,
                    source=ConstraintSource.NORMALIZER,
                    source_key=sk,
                    description=f"RelationIntent separation: {note}",
                )
            )
            existing_ids.add(cid)
        elif intent.kind in ("access", "open_connection"):
            ctype = (
                SpaceConnectionType.DOOR
                if intent.kind == "access"
                else SpaceConnectionType.OPEN
            )
            cid = _stable_pair_id(
                "rel-acc" if intent.kind == "access" else "rel-open", a_id, b_id
            )
            if cid in existing_ids:
                continue
            if access is None:
                access = AccessGraph(node_ids=[r.id for r in program.rooms])
            for r in program.rooms:
                if r.id not in access.node_ids:
                    access.node_ids.append(r.id)
            access.add_connection(
                SpaceConnection(
                    id=cid,
                    a=a_id,
                    b=b_id,
                    type=ctype,
                    required=hard,
                    weight=weight,
                    description=f"RelationIntent {intent.kind}: {note}",
                )
            )
            existing_ids.add(cid)
        # visual_connection: 预留

    updated = program.model_copy(
        update={
            "constraints": constraints,
            "access_graph": access,
        }
    )
    return updated.model_copy(update={"room_graph": _rebuild_room_graph(updated)})

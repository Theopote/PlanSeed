"""将 TopologyStrategy 物化为 RoomGraph / 权重提示。"""

from __future__ import annotations

from packages.schema.program import DesignProgram
from packages.schema.topology import RoomEdge, RoomGraph
from packages.schema.topology_strategy import TopologyStrategy, builtin_strategy
from solver.semantics.roles import is_kitchen, is_living, is_master_bedroom
from solver.topology.graph import build_graph_from_program


def _resolve_endpoint(program: DesignProgram, token: str) -> str | None:
    """策略边可用角色名；解析为真实 room_id。"""
    if any(r.id == token for r in program.rooms):
        return token
    key = token.lower()
    for r in program.rooms:
        if key in ("living", "living_room") and is_living(r):
            return r.id
        if key == "kitchen" and is_kitchen(r):
            return r.id
        if key in ("bedroom", "master", "master_bedroom") and (
            is_master_bedroom(r) or "卧" in (r.name or "")
        ):
            return r.id
        if key == "dining" and "餐" in (r.name or ""):
            return r.id
    return None


def apply_topology_strategy(
    program: DesignProgram,
    strategy: TopologyStrategy | str,
) -> DesignProgram:
    """
    合并策略边到 RoomGraph，写入 metrics 策略标签；不含坐标。
    """
    if isinstance(strategy, str):
        resolved = builtin_strategy(strategy)
        if resolved is None:
            raise ValueError(f"未知 TopologyStrategy：{strategy}")
        strategy = resolved

    base_graph = program.room_graph or build_graph_from_program(program)
    room_ids = list(base_graph.room_ids) or [r.id for r in program.rooms]
    edges = list(base_graph.edges)

    for e in strategy.room_graph_edges:
        a = _resolve_endpoint(program, e.source_id)
        b = _resolve_endpoint(program, e.target_id)
        if a is None or b is None or a == b:
            continue
        edges.append(
            RoomEdge(source_id=a, target_id=b, kind=e.kind, weight=e.weight)
        )
        if a not in room_ids:
            room_ids.append(a)
        if b not in room_ids:
            room_ids.append(b)

    graph = RoomGraph(room_ids=room_ids, edges=edges)
    cfg = program.solver_config.model_copy(
        update={
            "score_weight_overrides": dict(strategy.objective_weights or {}),
            "corridor_penalty": float(strategy.corridor_penalty),
        }
    )
    return program.model_copy(
        update={
            "room_graph": graph,
            "topology_plan": None,  # 强制 TopologyPlanner 重算
            "solver_config": cfg,
        }
    )


def list_builtin_strategies() -> list[TopologyStrategy]:
    from packages.schema.topology_strategy import BUILTIN_STRATEGIES

    return list(BUILTIN_STRATEGIES)


def tag_candidates_with_strategy(
    candidates: list,
    strategy: TopologyStrategy,
) -> None:
    for c in candidates:
        c.metrics["topology_strategy_id"] = strategy.id
        c.metrics["topology_strategy_label"] = strategy.label
        c.metrics["topology_corridor_penalty"] = float(strategy.corridor_penalty)
        for axis, w in (strategy.objective_weights or {}).items():
            c.metrics[f"strategy_weight_{axis}"] = float(w)
        if not c.metrics.get("selection_label"):
            c.metrics["selection_label"] = strategy.label

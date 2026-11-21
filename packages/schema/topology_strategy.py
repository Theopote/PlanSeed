"""TopologyStrategy — 生成前命名策略（不含坐标）。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.schema.topology import RoomEdge, RoomEdgeKind


class TopologyStrategyObjective(StrEnum):
    FAMILY_CORE = "family_core"
    PRIVACY = "privacy"
    DAYLIGHT_COURTYARD = "daylight_courtyard"


class TopologyStrategy(BaseModel):
    """
    AI / 规则提出的空间组织策略。

    物化为 RoomGraph delta + 软目标权重；经 TopologyPlanner → TopologyPlan。
    """

    id: str
    label: str
    objective: TopologyStrategyObjective
    description: str = ""
    room_graph_edges: list[RoomEdge] = Field(
        default_factory=list,
        description="追加/覆盖的 RoomGraph 边（无坐标）",
    )
    objective_weights: dict[str, float] = Field(
        default_factory=dict,
        description="七轴软权重微调，如 privacy=1.2",
    )
    corridor_penalty: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description=">1 更抑制走廊面积倾向（软）",
    )


# 内置三套概念策略（确定性，可被 AI 替换/微调）
BUILTIN_STRATEGIES: tuple[TopologyStrategy, ...] = (
    TopologyStrategy(
        id="family_core",
        label="家庭交流优先",
        objective=TopologyStrategyObjective.FAMILY_CORE,
        description="客厅作为公共核心，厨餐相连，交通尽量紧凑",
        room_graph_edges=[
            RoomEdge(source_id="living", target_id="kitchen", kind=RoomEdgeKind.CONNECTED, weight=2.0),
            RoomEdge(source_id="living", target_id="dining", kind=RoomEdgeKind.ADJACENT, weight=1.5),
        ],
        objective_weights={"circulation": 1.1, "spatial": 1.05},
        corridor_penalty=1.2,
    ),
    TopologyStrategy(
        id="privacy",
        label="私密性优先",
        objective=TopologyStrategyObjective.PRIVACY,
        description="公共靠入口，卧室集中安静区，避免穿越私人房间",
        room_graph_edges=[
            RoomEdge(source_id="living", target_id="bedroom", kind=RoomEdgeKind.FAR, weight=1.5),
            RoomEdge(source_id="kitchen", target_id="bedroom", kind=RoomEdgeKind.AVOID, weight=1.2),
        ],
        objective_weights={"privacy": 1.25, "circulation": 1.05},
        corridor_penalty=1.0,
    ),
    TopologyStrategy(
        id="daylight_courtyard",
        label="采光庭院优先",
        objective=TopologyStrategyObjective.DAYLIGHT_COURTYARD,
        description="主房间争取外墙与庭院联系，允许交通面积略增",
        room_graph_edges=[],
        objective_weights={"environment": 1.25, "spatial": 1.1},
        corridor_penalty=0.85,
    ),
)


def builtin_strategy(strategy_id: str) -> TopologyStrategy | None:
    for s in BUILTIN_STRATEGIES:
        if s.id == strategy_id:
            return s
    return None

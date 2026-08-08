"""
住宅默认 AccessGraph 派生 — Phase 2.1。

原则：
- 邻接 ≠ 通行：AdjacencyConstraint 不自动变 SpaceConnection
- 默认边多为 soft（required=False），供 SVG / 软评分 / 打包加权；
  硬必连仍由用户显式 SpaceConnection(required=True) 或 AccessConstraint 表达
- 判定只走 semantic_role / tags（及冻结 name 回退），不写新的 NLP
"""

from __future__ import annotations

from packages.schema.constraints import AccessConstraint
from packages.schema.program import DesignProgram
from packages.schema.room import RoomSpec
from packages.schema.topology import AccessGraph, SpaceConnection, SpaceConnectionType
from solver.semantics.roles import (
    is_dining,
    is_foyer,
    is_guest_bath,
    is_hall,
    is_kitchen,
    is_living,
    is_master_bath,
    is_master_bedroom,
)
from solver.topology.constants import ENTRY_NODE_ID


def is_bedroom(room: RoomSpec, *, allow_name_fallback: bool = True) -> bool:
    from packages.schema.room import SemanticRole
    from solver.semantics.roles import (
        TAG_BEDROOM,
        has_any_tag,
        has_role,
        is_elderly_bedroom,
    )

    if has_role(
        room,
        SemanticRole.BEDROOM,
        SemanticRole.MASTER_BEDROOM,
        SemanticRole.ELDERLY_BEDROOM,
    ):
        return True
    if is_master_bedroom(room, allow_name_fallback=allow_name_fallback):
        return True
    if is_elderly_bedroom(room, allow_name_fallback=allow_name_fallback):
        return True
    if has_any_tag(room, TAG_BEDROOM):
        return True
    if not allow_name_fallback:
        return False
    return "卧" in room.name or "睡" in room.name


def _hub_for_floor(rooms: list[RoomSpec]) -> RoomSpec | None:
    """通行枢纽：门厅 > 客厅 > 过厅 > 主卧（夜区回退）。"""
    for pred in (is_foyer, is_living, is_hall, is_master_bedroom):
        for r in sorted(rooms, key=lambda x: x.id):
            if pred(r):
                return r
    return None


def _pair_id(a: str, b: str, prefix: str) -> str:
    x, y = (a, b) if a <= b else (b, a)
    return f"{prefix}-{x}-{y}"


def derive_residential_access_graph(program: DesignProgram) -> AccessGraph:
    """
    从房间语义派生住宅通行偏好图（可与用户图合并前的默认）。

    同层：
      hub —DOOR→ bedroom / guest bath（soft）
      kitchen —OPEN→ dining（soft）
      master bedroom —DOOR→ master bath（soft）
    AccessConstraint.requires_exterior → entry —EXTERIOR_ENTRY→ room
    """
    graph = AccessGraph()
    seen: set[tuple[str, str, str]] = set()

    def add(conn: SpaceConnection) -> None:
        key = tuple(sorted((conn.a, conn.b))) + (conn.type.value,)
        if key in seen:
            return
        seen.add(key)
        graph.add_connection(conn)

    for fl in program.floors:
        rooms = program.rooms_on_floor(fl.id)
        if not rooms:
            continue
        hub = _hub_for_floor(rooms)
        if hub is not None:
            for room in rooms:
                if room.id == hub.id:
                    continue
                # 同层枢纽辐射：卧室/客卫/其它功能房 soft DOOR（可实现才落门）
                add(
                    SpaceConnection(
                        id=_pair_id(hub.id, room.id, "door"),
                        a=hub.id,
                        b=room.id,
                        type=SpaceConnectionType.DOOR,
                        required=False,
                        weight=1.0 if is_bedroom(room) or is_guest_bath(room) else 0.6,
                        description=f"默认：{hub.name}↔{room.name}通行",
                    )
                )

        kitchens = [r for r in rooms if is_kitchen(r)]
        dinings = [r for r in rooms if is_dining(r)]
        for k in kitchens:
            for d in dinings:
                if k.id == d.id:
                    continue
                add(
                    SpaceConnection(
                        id=_pair_id(k.id, d.id, "open"),
                        a=k.id,
                        b=d.id,
                        type=SpaceConnectionType.OPEN,
                        required=False,
                        weight=1.0,
                        description="默认：厨餐厅开敞连通",
                    )
                )

        masters = [r for r in rooms if is_master_bedroom(r)]
        mbaths = [r for r in rooms if is_master_bath(r)]
        for mb in masters:
            for bath in mbaths:
                add(
                    SpaceConnection(
                        id=_pair_id(mb.id, bath.id, "door"),
                        a=mb.id,
                        b=bath.id,
                        type=SpaceConnectionType.DOOR,
                        required=False,
                        weight=1.2,
                        description="默认：主卧↔主卫",
                    )
                )

    for c in program.constraints:
        if not isinstance(c, AccessConstraint):
            continue
        if c.requires_exterior:
            add(
                SpaceConnection(
                    id=f"ext-req-{c.room_id}",
                    a=ENTRY_NODE_ID,
                    b=c.room_id,
                    type=SpaceConnectionType.EXTERIOR_ENTRY,
                    required=c.hard,
                    weight=c.weight,
                    description="AccessConstraint.requires_exterior",
                )
            )

    return graph


def ensure_access_graph(program: DesignProgram) -> AccessGraph:
    """若 program.access_graph 为空则填入住宅默认（软边为主）。"""
    if program.access_graph is not None:
        return program.access_graph
    graph = derive_residential_access_graph(program)
    program.access_graph = graph
    return graph

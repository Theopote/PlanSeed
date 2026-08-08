"""
TopologyPlanner — RoomGraph → TopologyPlan（生成前）。

产出邻接簇、prefer/avoid 对、每层确定性 pack_order_hint。
不重划功能区；不生成门洞。
"""

from __future__ import annotations

from collections import defaultdict, deque

from packages.schema.program import DesignProgram
from packages.schema.topology import (
    AdjacencyCluster,
    RoomEdgeKind,
    RoomPair,
    TopologyPlan,
)
from solver.topology.graph import build_graph_from_program

# 参与「共域」连通分量的边类型
_CLUSTER_KINDS = frozenset(
    {RoomEdgeKind.ADJACENT, RoomEdgeKind.CONNECTED, RoomEdgeKind.NEAR}
)


class TopologyPlanner:
    def plan(self, program: DesignProgram) -> TopologyPlan:
        if program.topology_plan is not None:
            return program.topology_plan

        graph = build_graph_from_program(program)
        floor_of = self._floor_lookup(program)

        prefer_adjacent = self._prefer_pairs(graph)
        avoid_pairs = self._avoid_pairs(graph)
        clusters = self._clusters_by_floor(graph, floor_of)
        pack_order_hint = self._pack_orders(program, graph, floor_of)

        return TopologyPlan(
            clusters=clusters,
            prefer_adjacent=prefer_adjacent,
            avoid_pairs=avoid_pairs,
            pack_order_hint=pack_order_hint,
        )

    @staticmethod
    def _floor_lookup(program: DesignProgram) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for fl in program.floors:
            for rid in fl.room_ids:
                lookup[rid] = fl.id
        for room in program.rooms:
            if room.id not in lookup and room.floor_id:
                lookup[room.id] = room.floor_id
        return lookup

    @staticmethod
    def _pair_key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def _prefer_pairs(self, graph) -> list[RoomPair]:
        seen: set[tuple[str, str]] = set()
        pairs: list[RoomPair] = []
        for e in graph.edges:
            if e.kind != RoomEdgeKind.ADJACENT:
                continue
            key = self._pair_key(e.source_id, e.target_id)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(
                RoomPair(room_a_id=key[0], room_b_id=key[1], weight=e.weight)
            )
        pairs.sort(key=lambda p: (-p.weight, p.room_a_id, p.room_b_id))
        return pairs

    def _avoid_pairs(self, graph) -> list[RoomPair]:
        seen: set[tuple[str, str]] = set()
        pairs: list[RoomPair] = []
        for e in graph.edges:
            if e.kind not in (RoomEdgeKind.AVOID, RoomEdgeKind.FAR):
                continue
            key = self._pair_key(e.source_id, e.target_id)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(
                RoomPair(room_a_id=key[0], room_b_id=key[1], weight=e.weight)
            )
        pairs.sort(key=lambda p: (-p.weight, p.room_a_id, p.room_b_id))
        return pairs

    def _clusters_by_floor(
        self, graph, floor_of: dict[str, str]
    ) -> list[AdjacencyCluster]:
        """同层过滤后的 adjacent/connected/near 连通分量。"""
        adj: dict[str, set[str]] = defaultdict(set)
        nodes = set(graph.room_ids)
        for e in graph.edges:
            if e.kind not in _CLUSTER_KINDS:
                continue
            if e.source_id in nodes and e.target_id in nodes:
                adj[e.source_id].add(e.target_id)
                adj[e.target_id].add(e.source_id)

        # 先整栋连通分量，再按层切分
        visited: set[str] = set()
        clusters: list[AdjacencyCluster] = []
        for rid in sorted(nodes):
            if rid in visited:
                continue
            component: list[str] = []
            q = deque([rid])
            visited.add(rid)
            while q:
                cur = q.popleft()
                component.append(cur)
                for nb in sorted(adj.get(cur, ())):
                    if nb not in visited:
                        visited.add(nb)
                        q.append(nb)

            by_floor: dict[str, list[str]] = defaultdict(list)
            for cid in component:
                fid = floor_of.get(cid)
                if fid is None:
                    continue
                by_floor[fid].append(cid)
            for fid in sorted(by_floor):
                members = sorted(by_floor[fid])
                if len(members) >= 2:
                    clusters.append(AdjacencyCluster(floor_id=fid, room_ids=members))
                elif len(members) == 1 and len(adj.get(members[0], ())) > 0:
                    # 跨层边导致单层单点：仍不建簇
                    pass

        clusters.sort(key=lambda c: (c.floor_id, c.room_ids[0] if c.room_ids else ""))
        return clusters

    def _pack_orders(
        self,
        program: DesignProgram,
        graph,
        floor_of: dict[str, str],
    ) -> dict[str, list[str]]:
        """
        每层确定性打包顺序：邻接权重 hub BFS，同权按 room_id。
        """
        # 边权：仅 cluster kinds + adjacent 加权
        weight_of: dict[tuple[str, str], float] = {}
        for e in graph.edges:
            if e.kind not in _CLUSTER_KINDS and e.kind != RoomEdgeKind.ADJACENT:
                continue
            key = self._pair_key(e.source_id, e.target_id)
            # adjacent 优先抬升
            w = e.weight * (2.0 if e.kind == RoomEdgeKind.ADJACENT else 1.0)
            weight_of[key] = max(weight_of.get(key, 0.0), w)

        adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for (a, b), w in weight_of.items():
            adj[a].append((b, w))
            adj[b].append((a, w))
        for rid in adj:
            adj[rid].sort(key=lambda t: (-t[1], t[0]))

        degree_weight = {
            rid: sum(w for _, w in nbs) for rid, nbs in adj.items()
        }

        orders: dict[str, list[str]] = {}
        for fl in program.floors:
            room_ids = [
                r.id
                for r in program.rooms_on_floor(fl.id)
            ]
            # 补全 floor_of 未覆盖者
            for rid in room_ids:
                floor_of.setdefault(rid, fl.id)

            remaining = set(room_ids)
            order: list[str] = []

            while remaining:
                # 选剩余中度最高的 hub
                hub = min(
                    remaining,
                    key=lambda rid: (-degree_weight.get(rid, 0.0), rid),
                )
                # BFS from hub，仅在 remaining 内
                q: deque[str] = deque([hub])
                seen_local = {hub}
                while q:
                    cur = q.popleft()
                    if cur not in remaining:
                        continue
                    remaining.remove(cur)
                    order.append(cur)
                    for nb, _w in adj.get(cur, ()):
                        if nb in remaining and nb not in seen_local:
                            seen_local.add(nb)
                            q.append(nb)
                # 孤立点已在 BFS 中处理；若 hub 无邻居则仅自身

            orders[fl.id] = order
        return orders


def order_rooms_for_zone(
    room_ids: list[str],
    *,
    pack_order: list[str] | None,
    cluster_members: list[set[str]] | None = None,
) -> list[str]:
    """
    将 zone 内房间按拓扑 hint 排序：簇内成员靠前且相邻，其余按 hint / id。
    """
    if not room_ids:
        return []
    id_set = set(room_ids)
    hint = [rid for rid in (pack_order or []) if rid in id_set]
    leftover = sorted(id_set - set(hint))
    base = hint + leftover

    if not cluster_members:
        return base

    # 把同簇成员拉到连续块：按 hint 中首次出现的簇顺序
    placed: set[str] = set()
    result: list[str] = []
    for rid in base:
        if rid in placed:
            continue
        # 找包含 rid 的簇
        cluster = next((c for c in cluster_members if rid in c), None)
        if cluster is None:
            result.append(rid)
            placed.add(rid)
            continue
        # 按 base 顺序输出簇内成员
        for other in base:
            if other in cluster and other not in placed:
                result.append(other)
                placed.add(other)
    return result


def split_avoid_groups(
    rooms: list,
    avoid_pairs: list[RoomPair],
    *,
    id_attr: str = "spec",
) -> tuple[list, list] | None:
    """
    若存在 avoid 对且两者都在 rooms 中，尝试分成两组（各至少 1）。
    成功返回 (group_a, group_b)；无法干净分割则 None（留给 evaluator）。
    rooms 元素需有 .spec.id 或直接是带 id 的对象。
    """
    if len(rooms) < 2 or not avoid_pairs:
        return None

    def _rid(lr) -> str:
        if hasattr(lr, "spec"):
            return lr.spec.id
        return lr.id

    ids = {_rid(r) for r in rooms}
    relevant = [
        p
        for p in avoid_pairs
        if p.room_a_id in ids and p.room_b_id in ids
    ]
    if not relevant:
        return None

    # 取最高权 avoid 对作为种子
    seed = max(relevant, key=lambda p: (p.weight, p.room_a_id, p.room_b_id))
    a_ids = {seed.room_a_id}
    b_ids = {seed.room_b_id}

    # 其余房间按当前列表顺序轮流填入两边以平衡数量
    rest = [r for r in rooms if _rid(r) not in a_ids and _rid(r) not in b_ids]
    for i, r in enumerate(rest):
        if i % 2 == 0:
            a_ids.add(_rid(r))
        else:
            b_ids.add(_rid(r))

    group_a = [r for r in rooms if _rid(r) in a_ids]
    group_b = [r for r in rooms if _rid(r) in b_ids]
    if not group_a or not group_b:
        return None
    return group_a, group_b

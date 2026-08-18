# ADR-011 — Private Room Corridor Access Repair

## Status

**Implemented**（2026-08-18）。生成器修补 + RealizedAccessGraph PASSAGE 已接入；
benchmark 回归通过。剩余部分 valid 候选的穿卧室为结构不可避免，见 Implementation。

## Context

现状核对（均已用当前代码 + benchmark_program 实测，非推测）：

1. **走廊/循环空间目前是切分算法的副产品，不是主动规划的结果**：
   `solver/geometry/coverage.py::assign_residual_gaps_as_circulation` 的实现是
   "把房间切分完之后剩下的边角料标记为走廊"。没有任何机制保证"每个私密房间都能
   直接摸到一条走廊"。

2. **实测影响面是系统性的**：默认 benchmark_program、`candidate_count=64`，修补前
   Top-5 候选 **5/5（100%）** 存在 `private_through_count > 0`。

3. **门连接 Rule 1/2 只能防止最坏情况**（卧室直连卧室），防不住链式穿越。
   根因在更上游的"走廊有没有铺到该到的地方"。

## Decision

在 `assign_residual_gaps_as_circulation` 之后追加几何修补
`improve_private_room_corridor_access`（见 `docs/proposals/corridor-access-repair.md`）：

- 对无走廊邻接的 `private` 房间，从非 private 邻居借 0.9m 边切走廊
- Donor 限于 `wet` / `other` / `public`；排除 `stair-*`、`void-*`、`circ-*`
- 湿区 donor 优先；每层最多 1 次修补；不得侵入楼梯核
- 新走廊须接入现有循环网络（BFS 从走廊出发，禁止经其它 private 绕路）
- `apply_corridor_access_repair_if_safe`：修补后须通过完整 checker，否则回退
- RealizedAccessGraph 为 `circ-*` 生成 `circulation_passage` PASSAGE 边
- 隐私评分优先选择不经其它卧室的路径；区分 `unavoidable_private_through_count`

## Implementation（2026-08-18）

| 指标 | 修补前 | 修补后 |
|------|--------|--------|
| valid_ratio | ≈0.359 (23/64) | **0.359 (23/64)** 无回退 |
| Top-5 `private_through_count > 0` | 5/5 | **0/5** |
| valid 中 `private_through > 0` | — | 12/23，全部为 unavoidable |

**已尝试且回退**：将 `circ-*` 纳入 spanning tree 节点 → valid_ratio 跌至 11/64，
部分房间 unreachable；已回退，仅保留 spanning BFS 邻接排序（延后私密-私密边）。

## Consequences

- **不保证消除所有穿越**，只保证减少。邻居均为 private 或无可借面积时跳过。
- 修补后须重新跑 `resolve_placement_overlaps` 与完整 checker。
- 不解决走廊碎片形状凌乱；治本需「走廊先行切分」（独立提案）。
- 剩余 unavoidable 个案（如 F2 r7 经 r5 才能到达）需生成器级改动，非修补层可解。

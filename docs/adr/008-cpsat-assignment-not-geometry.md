# ADR-008 — CP-SAT scopes assignment, not geometry

## Status

Accepted（Phase 8.3 Research）

## Context

评审建议引入 CP-SAT。若用其直接生成房间矩形，会与确定性 packing、locks、repair 体系冲突，且难以解释局部几何失败。

## Decision

CP-SAT **只**用于离散归属 / 拓扑类问题：

- floor assignment
- zone assignment（后续）
- topology / hard adjacency / orientation eligibility（后续）

几何仍由 `LayoutGenerator`（Guillotine / MaxRect）+ Repair 完成。

默认 `normalize` / `FloorAssignmentSolver` 路径不变；CP-SAT 为 **opt-in research**：

```bash
uv sync --group research
```

```python
from solver.assignment import assign_floors_cpsat
```

## Consequences

- 依赖 `ortools` 进入 `research` 组，不强迫默认 runtime  
- 禁止宣称「CP-SAT 取代了 PlanSeed solver」  
- 后续 zone/topology CP-SAT 模块沿同一边界扩展

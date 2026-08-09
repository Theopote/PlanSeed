# Alpha Stabilization / Solver 2.0 Requalification

> **状态：▶ 进行中** · 总览：[roadmap.md](../roadmap.md)  
> **不是 Phase 9。** 暂停新功能；先把 Solver 2.0 能力面与 Alpha 默认产品语义重新对齐。

## 为什么现在停

7.2 / 7.5 / Phase 8（8.0–8.4）功能面已落地，但出现了 **默认行为漂移**：

| 问题 | 严重度 | 说明 |
|------|--------|------|
| Pareto 曾被设为默认 `rank_mode` | **P0** | 未显式选择「实验模式」时，Top-K / Top-1 / Compare 默认对象已变 |
| 身份签名不足以描述选优 | P1 | 仅有 `solver` / `generator` / `evaluation`；缺 `selection_version` |
| 「Phase 8 全部完成」与契约冻结冲突 | P1 | roadmap 仍要求改 ranking 须可追踪 bump |

## P0 处置（本轮）

1. **Alpha 默认**恢复：`SolverConfig.rank_mode = "axis"`  
   （score + 轴叙事 + 几何 diversity；8.1）  
2. **Pareto** 保留为 **Experimental / opt-in**：`rank_mode="pareto"`  
   - 目标复用七轴语言（禁止 Efficiency 别名）  
   - slot1 = 全局 top-score；slot2–k = Pareto crowding  
3. 新增 `SELECTION_VERSION`（默认 `axis-diversity-v1`）；候选 metrics / provenance 写入实际策略  
4. `SOLVER_VERSION` → `0.5`（Solver 2.0 能力面存在，但默认语义回稳）  
5. `EVALUATION_VERSION` **不变**（`residential-alpha-v1`；七轴规则未改）

```text
rank_mode:
  score     纯总分
  axis      ← Alpha default（最高分 + 轴优势 + 几何 diversity）
  pareto    ← Experimental（slot1=最高分 + 前沿 crowding）

默认路径：  Guillotine + axis selection
opt-in：    MaxRect · multi-gen pool · pareto · CP-SAT · Shapely irregular
```

## Requalification 清单（后续）

- [x] 默认 ranking ≠ Pareto  
- [x] `selection_version` 进入 `solver_identity` / provenance  
- [x] 固定 fixture：默认 Top-K 角色分布回归（axis）  
  （`solver/fixtures/topk_axis_roles.py` · `test_topk_axis_roles_regression.py`）  
- [ ] 文档：凡写「Phase 8 完成」须注明 **默认语义已 requalify**  
- [ ] 7.1.1 WebView2 Print Smoke（产品手测，独立于本项）  
- [ ] **禁止**在稳定化完成前开 Phase 9 / 新算法主线  

## 契约纪律（修订）

| 变更 | 必须 bump |
|------|-----------|
| 七轴权重 / Finding / 轴合成 | `evaluation_version` |
| 生成拓扑 / 默认 generator 行为 | `generator_version` 和/或 `solver_version` |
| Top-K / ranking / compare 默认对象 | **`selection_version`**（及必要时 `solver_version`） |

书面契约：[api-contract.md](../api-contract.md) · 评分：[scoring.md](../scoring.md)

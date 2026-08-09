# Alpha Stabilization / Solver 2.0 Requalification

> **状态：✅ P0 语义回稳已落地** · 下一关：[../alpha-v0.1-release-readiness.md](../alpha-v0.1-release-readiness.md)  
> **不是 Phase 9。** 默认行为回稳后，进入 Release Gate（验证与修正），不开新功能主线。

## 为什么停过一轮

7.2 / 7.5 / Phase 8（8.0–8.4）功能面已落地，但出现了 **默认行为漂移**：

| 问题 | 严重度 | 说明 |
|------|--------|------|
| Pareto 曾被设为默认 `rank_mode` | **P0** | 未显式选择「实验模式」时，Top-K / Top-1 / Compare 默认对象已变 |
| 身份签名不足以描述选优 | P1 | 仅有 `solver` / `generator` / `evaluation`；缺 `selection_version` |
| 「Phase 8 全部完成」与契约冻结冲突 | P1 | roadmap 仍要求改 ranking 须可追踪 bump |

## P0 处置（已完成）

1. **Alpha 默认**恢复：`SolverConfig.rank_mode = "axis"`  
2. **Pareto** = Experimental / opt-in（`experimental=True`）  
3. `SELECTION_VERSION` + 模式戳；`SOLVER_VERSION` → `0.5`  
4. `EVALUATION_VERSION` 不变（`residential-alpha-v1`）  
5. **`SolverProfile`**：`alpha-stable` / research-*；API `generate_layouts` pin Alpha Stable  

```text
Alpha Stable（产品默认）:
  Guillotine + axis + heuristic + rect + residential-alpha-v1

Experimental Lab:
  MaxRect · Pareto · CP-SAT · Shapely foundation
  （须 experimental=True 或显式 generators=）
```

## Requalification → Release Gate

语义回稳清单：

- [x] 默认 ranking ≠ Pareto  
- [x] `selection_version` / SolverProvenance strategy 层  
- [x] Top-K axis 角色回归  
- [x] Alpha 默认候选池 = Guillotine only  
- [x] `SolverProfile` + 产品路径 pin  
- [x] CP-SAT = assignment-only research  
- [x] 8.4 = Irregular Geometry Foundation（非端到端）  
- [ ] **8.4.1** Irregular Site Pipeline Integration  
- [ ] MaxRect **product qualification**  
- [ ] 7.1.1 WebView2 Print Smoke  
- [ ] 安装包 / `.planseed` 往返（见 Release Gate）  
- [ ] **禁止**在 Gate 完成前开 Phase 9  

完整 Gate 清单与通过标准 → [alpha-v0.1-release-readiness.md](../alpha-v0.1-release-readiness.md)

## 契约纪律

| 变更 | 必须 bump |
|------|-----------|
| 七轴权重 / Finding / 轴合成 | `evaluation_version` |
| 生成拓扑 / 默认 generator 行为 | `generator_version` 和/或 `solver_version` |
| Top-K / ranking / compare 默认对象 | **`selection_version`**（及必要时 `solver_version`） |

书面契约：[api-contract.md](../api-contract.md) · 评分：[scoring.md](../scoring.md)

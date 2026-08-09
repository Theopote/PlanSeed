# Phase 8 — Solver 2.0 / Design Kernel Next Generation

> **状态：▶ 8.2 Pareto Frontier ✅ · 下一 8.3 CP-SAT · 8.0–8.1 ✅ · 7.5 ✅ · 禁止 GA 进化生成**  
> 总览：[../roadmap.md](../roadmap.md) · Solver：[../solver.md](../solver.md) · ADR：[../adr/](../adr/)

## 原则

- 本阶段才吸收原评审中的**算法类**建议  
- **不要**一上来 GA / NSGA-II  
- **不要**用 CP-SAT 直接替代整个几何 solver  
- **不要**现在迁 Shapely / 整库 Rect engine  
- **禁止**把 Design Heuristic 说成 Code Compliance（无 Jurisdiction / CodeProfile 前）

## 顺序

```text
8.0-A LayoutGenerator Interface     ✅
  → 8.0-B MaxRect packing strategy    ✅
  → 8.0-C Generator Benchmark         ✅（Guillotine vs MaxRect）
8.1 Diversity Selection（top-score + diverse alternatives） ✅
8.2 Pareto Frontier（非支配集） ✅
8.3 CP-SAT Research（topology / assignment） ← 当前
8.4 Advanced Geometry（不规则场地才 Shapely）
```

| 项 | 主题 | 状态 |
|----|------|------|
| **8.0-A** | `LayoutGenerator` Protocol；Guillotine = Strategy | ✅ |
| **8.0-B** | MaxRect / Maximal Rectangles | ✅ |
| **8.0-C** | `layout-generation-benchmark` | ✅ |
| **8.1** | Diversity Selection | ✅ |
| **8.2** | Pareto Frontier | ✅ |
| **8.3** | CP-SAT Research | **← 当前** |
| **8.4** | Advanced Geometry（Shapely） | 更后 |

## 8.0-A — Generator Interface

目标：Guillotine 从「唯一生成器」变为「一个 Strategy」。

```python
@runtime_checkable
class LayoutGenerator(Protocol):
    @property
    def strategy_id(self) -> str: ...

    def generate(
        self,
        program: DesignProgram,
        seed: int,
        locks: LayoutLocks | None = None,
        topology: TopologyPlan | None = None,
    ) -> LayoutCandidate: ...
```

约定（相对早期草图的落地差异）：

| 草图 | 落地 |
|------|------|
| `Topology` | 仓库类型为 `TopologyPlan` |
| 显式 `config: SolverConfig` | 用 `program.solver_config`（单源） |
| `-> list[LayoutCandidate]` | **一次 seed → 一个 candidate**；多样本由 `run_pipeline` 换 seed |
| — | 保留 `locks`（Workbench 契约） |

落地：

- `solver/generators/base.py` — `LayoutGenerator`（`CandidateGenerator` 别名）  
- `GuillotineGenerator.strategy_id = "guillotine"`；可选注入 `topology`  
- `run_pipeline(..., generator=None)` — 默认 Guillotine，可注入其他 Strategy  

**不改变**默认几何 / 评分行为。

## 8.0-B — MaxRect ✅

第一个新增 strategy：**Maximal Rectangles**（不是遗传算法）。

- `solver/geometry/maxrects.py` — free-list update / BSSF / prune  
- `solver/generators/maxrect.py` — `MaxRectGenerator`（`strategy_id="maxrect"`）  
- 复用 Guillotine 的 StairCore / Zone / Topology；**仅替换叶子** `_layout_rooms`  
- `run_pipeline(..., generator=MaxRectGenerator())`  
- `generator_version = "maxrect-v1"`（与 Guillotine 的 provenance 区分）

理由：确定性 · 易 debug · 易 benchmark · 与 Guillotine 分布差异明显。

## 8.0-C — Generator Benchmark ✅

```bash
uv run python -m solver.benchmark --count 32
uv run python -m solver.benchmark --count 32 --json --out docs/baselines/layout_generation_guillotine_vs_maxrect.json
```

模块：`solver/benchmark/layout_generation.py`

| 指标 | 含义 |
|------|------|
| valid_rate | 通过硬约束比例 |
| hard_violation_rate | 含 hard violation 的候选比例 |
| area_fit | valid 上 mean `area_accuracy` |
| mean_aspect_ratio_penalty / aspect_ratio_quality | 长宽比惩罚（后者 `1/(1+p)`） |
| circulation | mean `circulation_score` |
| orientation | mean `orientation_satisfaction` |
| diversity | 几何指纹去重数 / generated |
| runtime_s | 墙钟时间 |

基线快照：`docs/baselines/layout_generation_guillotine_vs_maxrect.json`  
**禁止**凭感觉宣称某 strategy 全面更优；以报告数字为准。

## 8.1 — Diversity Selection ✅

排序不再只问「谁总分最高」。

```text
1. 最高总分          selection_role=top_score
2. 流线 / 隐私 / 朝向  相对 top 有明显轴优势且几何不雷同
3. 几何 diversity    填满 return_top_k
```

- `solver/optimization/diversity_select.py`
- `rank_candidates(..., axis_alternatives=True)`（默认）
- 候选 `metrics.selection_role` / `selection_label`；CandidateStrip 展示标签
- **不是** Pareto（8.2）

## 8.2 — Pareto Frontier ✅

静态非支配选择（**不是** NSGA-II 进化）：

| 目标 | DesignScore 字段 |
|------|------------------|
| Efficiency | `spatial_score` |
| Privacy | `privacy_score` |
| Circulation | `circulation_score` |
| Environment | `environment_score` |

- `solver/optimization/pareto.py` — `pareto_front` / crowding / `select_pareto_frontier`
- `SolverConfig.rank_mode = "pareto"`（默认）；`axis` 保留 8.1；`score` 纯总分
- `run_pipeline(..., generators=[GuillotineGenerator(), MaxRectGenerator()])` 合并池再选
- 标签：`selection_role=pareto` · `selection_label`（如「效率更好 · 流线更好」）

## 8.3–8.4（摘要）

- **8.3**：CP-SAT 做 floor/zone/topology/adjacency；几何仍 packing + repair ← 当前预告  
- **8.4**：不规则场地 / 庭院多边形才考虑 Shapely  

## 明确不做（Phase 8）

- Code Compliance（「三层必须电梯」等）  
- 无 Jurisdiction / CodeProfile / Rule / Source / Version / Applicability 前禁止声称「符合某规范」

## Definition of Done（8.0）

- [x] `LayoutGenerator` Protocol  
- [x] `GuillotineGenerator` 实现该接口（含 `strategy_id`）  
- [x] `run_pipeline` 可注入 generator  
- [x] 默认路径仍为 Guillotine，行为不变  
- [x] 8.0-B MaxRect
- [x] 8.0-C Generator Benchmark
- [x] 8.1 Diversity Selection
- [x] 8.2 Pareto Frontier
- [ ] 8.3 CP-SAT Research

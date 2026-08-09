# Phase 8 — Solver 2.0 / Design Kernel Next Generation

> **状态：✅ 能力面 8.0–8.4 已落地 · MaxRect 未产品验收 · ▶ [phase-8.5](phase-8.5-alpha-stabilization.md) requalify**  
> 总览：[../roadmap.md](../roadmap.md) · Solver：[../solver.md](../solver.md) · ADR：[../adr/](../adr/)

## 原则

- 本阶段才吸收原评审中的**算法类**建议  
- **不要**一上来 GA / NSGA-II  
- **不要**用 CP-SAT 直接替代整个几何 solver  
- **不要**把整库 Rect engine 迁到 Shapely（8.4 仅为 opt-in）  
- **禁止**把 Design Heuristic 说成 Code Compliance（无 Jurisdiction / CodeProfile 前）

## 顺序

```text
8.0-A LayoutGenerator Interface     ✅
  → 8.0-B MaxRect packing strategy    ✅ 实现 / ❌ 未产品验收
  → 8.0-C Generator Benchmark         ✅（Guillotine vs MaxRect；暴露 MaxRect 比例劣化）
8.1 Diversity Selection（top-score + diverse alternatives） ✅
8.2 Pareto Frontier（非支配集） ✅ Experimental
8.3 CP-SAT Research（floor assignment opt-in） ✅
8.4 Advanced Geometry（不规则场地 Shapely opt-in） ✅
```

| 项 | 主题 | 状态 |
|----|------|------|
| **8.0-A** | `LayoutGenerator` Protocol；Guillotine = Strategy | ✅ |
| **8.0-B** | MaxRect / Maximal Rectangles | ✅ 实现 · **❌ product qualified** |
| **8.0-C** | `layout-generation-benchmark` | ✅（基线已冻结；结论见下） |
| **8.1** | Diversity Selection | ✅ Alpha 默认 |
| **8.2** | Pareto Frontier | ✅ Experimental |
| **8.3** | CP-SAT Research | ✅ |
| **8.4** | Advanced Geometry（Shapely） | ✅ |

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

## 8.0-B — MaxRect（实现 ✅ · 产品验收 ❌）

第一个新增 strategy：**Maximal Rectangles**（不是遗传算法）。

- `solver/geometry/maxrects.py` — free-list update / BSSF / prune  
- `solver/generators/maxrect.py` — `MaxRectGenerator`（`strategy_id="maxrect"`）  
- 复用 Guillotine 的 StairCore / Zone / Topology；**仅替换叶子** `_layout_rooms`  
- `run_pipeline(..., generator=MaxRectGenerator())`  
- `generator_version = "maxrect-v1"`（与 Guillotine 的 provenance 区分）

```text
MaxRect implementation      ✅
MaxRect product qualified   ❌
```

**正确表述：** 代码路径可用、可 benchmark；**不得**写成 Alpha 默认或「已验证更优/可用」。  
Alpha 默认生成器仍为 **Guillotine**。MaxRect 仅 research / opt-in。

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
| circulation / privacy / environment | 轴分均值 |
| orientation | mean `orientation_satisfaction` |
| mean_repair_count | mean `connection_repairs` |
| diversity | 几何指纹去重数 / generated |
| runtime_s | 墙钟时间 |

基线快照：

- **遗留单 case：** `docs/baselines/layout_generation_guillotine_vs_maxrect.json`（≈ B03）  
- **资格套件：** [layout-benchmark-suite-v1.md](../baselines/layout-benchmark-suite-v1.md)  
  `uv run python -m solver.benchmark --suite v1 --count 32|64`

| | Guillotine | MaxRect（单 case B03，n=32） |
|--|------------|------------------------------|
| valid_rate | 1.0 | 1.0 |
| area_fit | 0.7533 | 0.7518 |
| aspect_ratio_quality | 0.037 | **0.007** |
| **mean_aspect_ratio_penalty** | **28.67** | **166.79** |
| circulation | 75.59 | 75.38 |
| top_score | 92.31 | 89.08 |
| mean_score | 88.24 | 87.17 |

**结论：** 单 case 已暴露 MaxRect 长宽比惩罚约 5.8× 更差 → **未产品验收**。  
进入 Alpha candidate pool 前必须过 **Layout Benchmark Suite v1**（B01–B12，n=32/64），不得只看 B03。

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

## 8.2 — Pareto Frontier ✅（Experimental / opt-in）

静态非支配选择（**不是** NSGA-II 进化；**不是** Alpha 默认）：

| 目标 | DesignScore 字段 | 标签 |
|------|------------------|------|
| Program | `program_score` | 功能配置更好 |
| Spatial | `spatial_score` | 空间品质更好 |
| Circulation | `circulation_score` | 流线更好 |
| Privacy | `privacy_score` | 私密性更好 |
| Environment | `environment_score` | 朝向更好 |

**禁止**另造 Efficiency 等第二套评分语义（`spatial_score ≠ efficiency`）。

产品截断：

```text
slot 1   = 全局最高总分（top_score）
slot 2–k = 非支配集 crowding（pareto）
```

- `solver/optimization/pareto.py` — `pareto_front` / crowding / `select_pareto_frontier`
- `SolverConfig.rank_mode = "pareto"`（**Experimental**；Alpha 默认仍为 `axis`）
- `run_pipeline(..., generators=[GuillotineGenerator(), MaxRectGenerator()])` 合并池再选
- `selection_version=pareto-top1-axes-v2`
- 稳定化：见 [phase-8.5-alpha-stabilization.md](phase-8.5-alpha-stabilization.md)

## 8.3 — CP-SAT Research ✅

```text
RequirementSpec / ProjectSpec
      ↓
CP-SAT Floor Assignment（opt-in research）
      ↓
DesignProgram
      ↓
Geometric Packing（Guillotine / MaxRect）
      ↓
Repair → Evaluation
```

- 模块：`solver/assignment/cpsat_floor.py`
- 依赖：`uv sync --group research`（ortools）
- **默认** normalize 仍用 `FloorAssignmentSolver`；CP-SAT **不**自动接入
- 硬：FloorConstraint / floor_id / room_ids  
  软：preference · adjacency 同层 · kitchen/garage 底层 · master 上层
- ADR：[adr/008-cpsat-assignment-not-geometry.md](../adr/008-cpsat-assignment-not-geometry.md)

后续可扩：zone assignment · topology · orientation eligibility — **仍禁止**输出坐标。

## 8.4 — Advanced Geometry ✅

默认仍为 Rect engine。Shapely **opt-in**：

- Schema：`Point2D` / `Polygon2D`；`SiteSpec.site_polygon` / `buildable_polygon`
- 模块：`solver/geometry/irregular.py`
  - 均匀退线 inset
  - 轴对齐矩形 containment
  - **正交**多边形 → free rects（供 packing 消费，不改写 Guillotine）
- 依赖：`uv sync --group research`（shapely）
- ADR：[adr/009-rect-default-shapely-irregular.md](../adr/009-rect-default-shapely-irregular.md)

**禁止**把整个 Rect / packing 内核迁到 Shapely。

## 明确不做（Phase 8）

- Code Compliance（「三层必须电梯」等）  
- 无 Jurisdiction / CodeProfile / Rule / Source / Version / Applicability 前禁止声称「符合某规范」

## Definition of Done（8.0）

- [x] `LayoutGenerator` Protocol  
- [x] `GuillotineGenerator` 实现该接口（含 `strategy_id`）  
- [x] `run_pipeline` 可注入 generator  
- [x] 默认路径仍为 Guillotine，行为不变  
- [x] 8.0-B MaxRect **implementation**（**未** product qualify；aspect penalty 劣化）
- [x] 8.0-C Generator Benchmark
- [x] 8.1 Diversity Selection
- [x] 8.2 Pareto Frontier
- [x] 8.3 CP-SAT Research
- [x] 8.4 Advanced Geometry

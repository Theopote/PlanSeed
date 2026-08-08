# Solver 架构

## 概述

Solver 是纯 Python domain 模块，**不依赖 FastAPI、Ollama 或 React**。

参考算法来源：`reference/floorplan-generator.html` 中的 `layoutRooms`、`layoutFloor`、`generateLayouts`。该原型使用递归 Guillotine 切分 + 0.3m snap + 湿区跨层 x 对齐 + 楼梯固定 x 区间。

在 v2 架构中，该算法是 **CandidateGenerator 的一种实现**，而非整个 solver。

## 核心接口

### CandidateGenerator

```python
class CandidateGenerator(Protocol):
    def generate(self, program: DesignProgram, seed: int) -> LayoutCandidate: ...
```

Phase 1 实现：`GuillotineGenerator`（`solver/generators/guillotine.py`）

未来可扩展：

- `GridGenerator`
- `ZoneGenerator`
- `GraphEmbeddingGenerator`
- `OptimizationGenerator`

### ConstraintChecker

```python
class ConstraintChecker(Protocol):
    def check(self, program: DesignProgram, candidate: LayoutCandidate) -> CandidateValidation: ...
```

Hard violation → `valid=False`。输出必须含 `constraint_id`、`room_ids`、`measured_value`、`required_value`，供 UI 解释失败原因。

### Evaluator

```python
class Evaluator(Protocol):
    def evaluate(self, program: DesignProgram, candidate: LayoutCandidate) -> DesignScore: ...
```

评价模块独立文件，避免单一巨大 `compute_score()`：

```text
solver/evaluation/
├── geometry.py      # Phase 1
├── adjacency.py     # Phase 1
├── vertical.py      # Phase 1（湿区/楼梯对齐）
├── site.py          # Phase 1
├── circulation.py   # 后续
├── orientation.py   # 后续
├── privacy.py       # 后续
└── score.py         # 聚合 + Protocol
```

## 流水线

```text
ProjectSpec
    │
    ▼ normalize()          solver/program/normalize.py
DesignProgram
    │
    ├── build_room_graph()
    │
    ▼ generate × N         CandidateGenerator.generate(program, seed)
LayoutCandidate[]
    │
    ▼ validate             ConstraintChecker.check()
    │
    ▼ evaluate             Evaluator.evaluate()
    │
    ▼ rank                 rank_candidates(top_k)
Top K candidates
```

## Architectural Zones（Phase 1.5 P3）

```text
StairCore → free rects → ZonePlanner 整栋共享 (day/night/service) → Guillotine within zones
```

| Zone | 房间来源 |
|------|----------|
| day | PUBLIC |
| night | PRIVATE / 书房 |
| service | WET / garage / SERVICE |
| circulation | StairCore（generated） |

Guillotine 降级为 **RoomLayout strategy**，不再独自决定整栋组织。

## Quality regression（Phase 1.5）


正式门槛集中在 `solver/tests/quality_baselines.py`，由 `test_quality_regression.py` 执行。

当前默认（基准 11×13 两层，N=32）：

| 指标 | 门槛 | 实测基线 |
|------|------|----------|
| valid_ratio | ≥ 0.70 | ≈ 0.875 |
| distinct layouts | ≥ 8 | 32 |
| distinct valid | ≥ 8 | 28 |
| Top-5 hard violations | 0 | 0 |
| Top-5 area_accuracy | ≥ 0.70 | ≈ 0.86 |
| core placements | ≥ 2 | 5 |

`valid >= 1` / `distinct > 1` 仅作 smoke；质量以本表为准。收紧阈值前先更新 `MEASURED_BASELINE`。

## Constraint 生命周期（强制）


每新增一条 constraint 必须走通：

```text
User Requirement
  → Schema
  → Normalizer（source / source_key）
  → Constraint
  → Generator 使用  和/或  Evaluator 评价
  → Score / Validation
  → 可解释结果
```

禁止：schema/constraint 存在但 solver 忽略。

| Constraint | Checker | Evaluator |
|------------|---------|-----------|
| Adjacency hard/soft | ✓ | adjacency metrics |
| Orientation hard | ✓ | — |
| Orientation soft | — | **orientation.py** ✓ |
| Area / Width | ✓ | geometry |
| Alignment / stair / wet | ✓ | vertical |
| Site / setbacks | boundary hard | **site.py**（非常量） |

## Diversity（预留）

Phase 1 的 `layout_similarity` 使用绝对米差 / 5m，对小住宅够用。
未来应改为 footprint 归一化，并加入 topology similarity（邻接、core 区位）。暂非 P0。

## RequirementSpec uncertainty（Phase 1.5）


`normalize_requirements()` 必须真正使用 `assumptions` / `unknowns`：

| 情况 | 行为 |
|------|------|
| 未指定 `household.bedrooms` 等 | 应用住宅默认，**写入 assumption** |
| 未指定 `site.width` / `site.depth` | **写入 unknown**，不默认 11×13，`can_solve=False` |
| 未指定房间面积 | 默认面积 + assumption |
| 未提供空间清单 | 基准程序 + assumption `spaces.program` |

返回 `RequirementsNormalizeResult`；需要 program 时用 `normalize_requirements_to_program()`（缺地块则抛 `IncompleteRequirementsError`）。

决策痕迹同步挂到 `DesignProgram.assumptions` / `unknowns`。

## FloorAssignment（Phase 1.5）


楼层归属由独立 `FloorAssignmentSolver` 完成，**不在 Generator 内猜测**。

```text
rooms + floors + constraints
        ↓
explicit FloorConstraint / room_ids / floor_id / preference
        ↓
implicit residential rules（可解释 rule_id）
        ↓
FloorAssignment
        ↓
floor.room_ids + RoomSpec.floor_id
```

住宅默认规则（第一版）：

| 规则 | 楼层 |
|------|------|
| PUBLIC / kitchen / dining / garage / elderly bedroom | F1 |
| PRIVATE / master bedroom / study | F2（上层） |
| 主卫 | 跟随主卧 |
| 其他卫浴 | wet stacking / 跟随私密区 |

每条决策含 `source` / `source_key` / `rule_id` / `reason`，写入 `DesignProgram.floor_assignment`。

## GuillotineGenerator


来自 `reference/floorplan-generator.html`：

1. **StairCore（非整层条带）**：默认约 `1.8 × 4.2`，区位 `N/S/E/W/center` 由 seed 选择，跨层对齐完整 AABB
2. **剩余矩形**：从 footprint 挖去核心后做正交分解
3. **ZonePlanner（整栋共享）**：按全楼 day/night/service 面积权重切分一次；各层只绑定本层房间。SERVICE 矩形跨层一致 → `wet_zone_*` 对齐
4. **Guillotine within zones**：在各 zone 矩形内递归切分
5. **确定性**：`rng = random.Random(seed)`；相同 program+seed → 相同 candidate

输出映射到 `RoomPlacement`，不修改 `RoomSpec`。

## 空间关系图

```text
Program → RoomGraph → Zoning → Geometry
```

`build_room_graph()` 从 explicit constraints 与 room category 构建初始图。Phase 1 的 Guillotine 生成器仍可使用原型条带分区逻辑；后续 ZoneGenerator 将更充分利用 RoomGraph。

## 几何模块

```text
solver/geometry/
├── rect.py    # Rect2D 复用 / 几何运算（Phase 1 扩展）
└── snap.py    # snap 函数（Phase 1）
```

## 测试要求（Phase 1）

以下模块必须有单元测试：

- schema ✓（Phase 0）
- geometry
- constraints
- room_graph
- generator
- validation
- evaluation
- ranking

基准用例（来自旧手册 Step 1）：

- 用地 11m × 13m，两层
- F1：客厅 24㎡、餐厅厨房 16㎡(wet)、卫生间 4㎡(wet)、车库 15㎡
- F2：主卧 18㎡、主卫 5㎡(wet)、次卧×2 12㎡、公卫 4㎡(wet)、书房 9㎡
- 断言：湿区 x 对齐、无重叠、在界内、楼梯 x 区间一致、外墙效率 ≈ 99.6%

## Phase 0 状态

- ✅ 接口 Protocol 定义
- ✅ `normalize()` + `build_room_graph()` 基础实现
- ✅ `rank_candidates()` 基础实现
- ⏳ GuillotineGenerator — Phase 1
- ⏳ ConstraintChecker 实现 — Phase 1
- ⏳ Evaluator 各模块 — Phase 1

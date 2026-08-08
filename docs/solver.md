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
StairCore → free rects → ZonePlanner（功能区 + 技术湿区条带）→ Guillotine within zones
```

| Zone（功能） | 房间来源 | WetStack（技术，可选） |
|------|----------|------------------------|
| day | PUBLIC、厨房 | 厨房 → WS1 |
| night | PRIVATE、书房、主卫 | 主卫 → WS1 |
| service | 客卫、洗衣、车库 | 客卫/洗衣 → WS1 |
| circulation | StairCore（generated） | — |

`WetStackGroup` 与功能区分离：厨房与主卫可同属 WS1，却分属 DAY / NIGHT。  
`LayoutCandidate.wet_stacks` 承载竖向服务对齐（`WetStack.id / anchor_rect / floor_ids / member_room_ids`）；MVP `max_wet_stacks=1`。各层 `wet_zone_*` 仅为兼容镜像。

Guillotine 降级为 **RoomLayout strategy**，不再独自决定整栋组织。

## Quality regression（Phase 1.5）


正式门槛集中在 `solver/tests/quality_baselines.py`，由 `test_quality_regression.py` 执行。

当前默认（基准 11×13 两层，N=32）：

| 指标 | 门槛 | 实测基线 |
|------|------|----------|
| valid_ratio | ≥ 0.70 | ≈ 1.0 |
| distinct layouts | ≥ 8 | 32 |
| distinct valid | ≥ 8 | 32 |
| Top-5 hard violations | 0 | 0 |
| Top-5 area_accuracy | ≥ 0.60 | ≈ 0.63+ |
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

Phase 1.5 的 `layout_similarity` 使用 `LayoutSignature`：坐标按 buildable 宽高归一化（dx/W, dy/D, …），并纳入 core 区位。

## RequirementSpec uncertainty（Phase 1.5）


`normalize_requirements()` 必须真正使用 `assumptions` / `unknowns`：

| 情况 | 行为 |
|------|------|
| 未指定 `household.bedrooms` 等 | 应用住宅默认，**写入 assumption** |
| 未指定 `site.width` / `site.depth` | **写入 unknown**，不默认 11×13，`can_solve=False` |
| 未指定房间面积 | 默认面积 + assumption |
| 未提供空间清单 | unknown `spaces.program`（不静默套 benchmark） |
| Demo / 回归基准 | `solver.fixtures.benchmark` 显式 fixture |

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

住宅默认规则（第一版；**判定看 tags，不看 name NLP**）：

| 规则 | 楼层 |
|------|------|
| PUBLIC / kitchen / dining / garage / elderly bedroom | F1 |
| PRIVATE / master bedroom / study | F2（上层） |
| 主卫 | 跟随主卧 |
| 其他卫浴 | wet stacking / 跟随私密区 |

语义入口：`solver/semantics/roles.py`（tags 优先；中文 name 回退为冻结 MVP）。  
例：`name="父母房"` + `tags=[bedroom, elderly_accessible]` → 地面层；无 tags 时不靠「父母」二字推断。

每条决策含 `source` / `source_key` / `rule_id` / `reason`，写入 `DesignProgram.floor_assignment`。

## GuillotineGenerator


来自 `reference/floorplan-generator.html`：

1. **StairCore（非整层条带）**：默认约 `1.8 × 4.2`，区位 `N/S/E/W/center` 由 seed 选择，跨层对齐完整 AABB
2. **剩余矩形**：从 footprint 挖去核心后做正交分解
3. **ZonePlanner**：功能区按层打包（空区回收）；产出 `BuildingZonePlan.wet_stacks`（≠ 功能 SERVICE）；Guillotine 写入 `LayoutCandidate.wet_stacks` 并镜像 `wet_zone_*`
4. **TopologyPlan**：邻接序驱动区内打包（替代 shuffle）；avoid 对尽量分半
5. **Guillotine within zones**：在各功能 zone 矩形内递归切分
6. **确定性**：拓扑序不依赖 seed；`rng` 仅扰动切分几何；相同 program+seed → 相同 candidate

输出映射到 `RoomPlacement`，不修改 `RoomSpec`。

## 空间关系图

```text
DesignProgram → FloorAssignment → Semantic RoomGraph → AccessGraph
  → ZonePlanner → Core → Graph-aware ordering → Guillotine
  → ConnectionResolver → DoorOpening → AccessibilityValidator → Evaluator
```

- **2.0**：`TopologyPlan` 替换纯 shuffle（hub BFS / 簇连续）
- **2.0.1**：邻接簇作为 **slicing group** 整组切分（如 K+D+L）；组内可再细分
- **2.1**：住宅默认 AccessGraph（软边）+ 高连通度打包 + `circulation_score`；硬必连仍显式
- **2.1.1**：`ConnectionResolver` 局部共边修补（缝隙闭合 / 短边加长）；远距不修
- **下一步**：更强 topology→geometry（跨区重切）；仍禁止为门全局重优化
- **2A**：geometry → 共边校验 → `DoorOpening`（禁止为门重优化房间）
- **ExteriorEntry**：交通起点（`entrance_edge` / `road_edges`）；**≠** StairCore
- **延后**：跨区 / 全局为连通改切分

门洞：先校验共边再标注；禁止矩形→直接画门。

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

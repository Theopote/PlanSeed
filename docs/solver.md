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

## GuillotineGenerator 算法要点（Phase 1 迁移）

来自 `reference/floorplan-generator.html`：

1. **楼梯/玄关条带**：每层固定 x 区间 `[0, stair_width]`
2. **湿区条带**：第一层计算 `wetRatio = wet_area / (wet + other)`，其余层复用 → x 方向对齐
3. **递归切分**：`layoutRooms` 按面积权重二分，选更接近正方形的切分方向，snap 到 `grid_module`（默认 0.3m）
4. **确定性**：shuffle 等随机操作必须使用传入 seed

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

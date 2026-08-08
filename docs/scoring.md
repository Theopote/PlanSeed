# 评分体系

## 设计原则

1. **Evaluator 独立层**：不修改 candidate，只解释质量。
2. **多指标分解**：返回 `DesignScore` 结构，而非单一数字。
3. **Hard / Soft 分离**：Hard 违反在 `ConstraintChecker` 处理；Evaluator 对 soft 约束扣分。

## DesignScore 结构

```python
DesignScore
├── geometry_score
├── adjacency_score
├── circulation_score      # Phase 2+ 实现，Phase 1 可为 0
├── orientation_score        # OrientationConstraint 满足度
├── privacy_score            # 后续
├── vertical_score
├── site_score               # setback/envelope，非常量
├── total_score
├── metrics: DesignMetrics
├── warnings[]
└── violations[]             # soft 违反摘要
```

## 第一阶段 Metrics（Phase 1 实现）

### Geometry (`evaluation/geometry.py`)

| Metric | 说明 |
|--------|------|
| `area_accuracy` | 面积**份额**与目标权重的一致性（非绝对 m²） |
| `aspect_ratio_penalty` | 长宽比 > 2.2 惩罚 |
| `compactness` | 紧凑度（perimeter efficiency） |
| `perimeter_efficiency_pct` | compactness × 100 |
| `slender_room_count` | 狭长房间数 |

#### area_accuracy 语义

Guillotine 按 `target_area` **权重**切分可建区域，实际平方米通常不等于目标值
（楼梯占位、整层填满）。因此：

```text
area_accuracy = 1 - TV(actual_share, target_share)
```

其中 TV 为 total variation distance。按楼层计算后取平均。
系统生成的 circulation（`source=generated`）不参与份额计算。

## Ranking Diversity

`rank_candidates` 默认启用：

```text
min_diversity_threshold = 0.85
```

贪心选取 Top K：跳过与已选方案 `layout_similarity >= threshold` 的候选。
设为 `None` 则纯分数排序。配置项：`SolverConfig.min_diversity_threshold`。

### Orientation (`evaluation/orientation.py`)

| Metric | 说明 |
|--------|------|
| `orientation_satisfaction` | 加权朝向满足率（贴 buildable 外墙） |
| soft violations | 未满足的 soft OrientationConstraint |

坐标系：`y=0` 北，`y` 增大向南；`x=0` 西。

### Site (`evaluation/site.py`)

| Metric | 说明 |
|--------|------|
| `setback_compliance` | 程序房间落在 buildable 内比例 |
| `setback_info_provided` | 是否用户提供了退界；未提供时 site_score ≤ 95 |

不再使用 `site_score = 100` 常量。

### Adjacency (`evaluation/adjacency.py`)


| Metric | 说明 |
|--------|------|
| `required_adjacency_satisfaction` | hard 邻接满足率 |
| `preferred_adjacency_satisfaction` | soft 邻接满足率 |

### Vertical (`evaluation/vertical.py`)

| Metric | 说明 |
|--------|------|
| `stair_alignment` | 楼梯 x 轴跨层对齐 |
| `wet_zone_alignment` | 湿区 x 轴跨层对齐 |

### Site (`evaluation/site.py`)

| Metric | 说明 |
|--------|------|
| `setback_compliance` | 退线合规率 |

## 后续 Metrics（不在 Phase 1）

- daylight
- circulation（走廊长度）
- privacy（动静分区）
- exterior wall access

## 与参考原型的关系

`reference/floorplan-generator.html` 的 `computeScore` 实现了：

- 外墙周长效率 = `4×sqrt(面积) / 实际周长 × 100%`
- 长宽比 > 2.2 房间标记
- 湿区 x 对齐消息

Phase 1 将这些逻辑拆分迁移：

- 效率 / 紧凑度 → `geometry.py` / `site.py`
- 长宽比 → `geometry.py` → `aspect_ratio_penalty`
- 湿区对齐 → `vertical.py` → `wet_zone_alignment`

## Total Score 聚合（Phase 1 建议权重）

```text
total = (
    0.35 × geometry_score +
    0.20 × adjacency_score +
    0.20 × vertical_score +
    0.15 × site_score +
    0.10 × (circulation + orientation + privacy)  # 初期为 0
)
```

权重可配置，存于 `SolverConfig` 或 `PreferencesSpec`（后续）。

## Hard vs Soft

| 类型 | 处理模块 | 结果 |
|------|----------|------|
| Hard constraint 违反 | ConstraintChecker | `valid=False`，不参与正常排名 |
| Soft constraint 违反 | Evaluator | 扣分 + `soft_violations[]` |
| 警告（非约束） | Evaluator | `warnings[]`（如狭长房间） |

## UI 展示（Phase 3）

- Candidate Strip：显示 `total_score` 简写（A 91, B 89…）
- Inspector：展开各分项 score + metrics + violations
- 失败 candidate：展示 `hard_violations` 详情

## Phase 0 状态

- ✅ `DesignScore` / `DesignMetrics` Pydantic 模型
- ✅ `Evaluator` Protocol 定义
- ⏳ 各 evaluation 模块实现 — Phase 1

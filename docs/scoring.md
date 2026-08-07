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
├── orientation_score        # Phase 2+
├── privacy_score            # Phase 2+
├── vertical_score
├── site_score
├── total_score
├── metrics: DesignMetrics
├── warnings[]
└── violations[]             # soft 违反摘要
```

## 第一阶段 Metrics（Phase 1 实现）

### Geometry (`evaluation/geometry.py`)

| Metric | 说明 |
|--------|------|
| `overlap_count` | 房间重叠数 |
| `boundary_violation` | 越界房间数 |
| `area_error` | 面积偏差累计 |
| `min_width_violation` | 宽度不足数 |
| `aspect_ratio_penalty` | 长宽比 > 2.2 惩罚 |
| `compactness` | 紧凑度 |

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

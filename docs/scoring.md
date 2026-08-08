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
├── circulation_score        # Realized + AccessIntent
├── orientation_score
├── privacy_score            # Phase 3：路径隐私过渡
├── vertical_score
├── site_score
├── program_fit_score        # Phase 3
├── space_efficiency_score   # Phase 3
├── layout_stability_score   # Phase 3（repair 扰动）
├── total_score
├── metrics: DesignMetrics
├── explanations[]           # 分项简述
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
| `orientation_satisfaction` | 加权朝向满足率（**世界** cardinal，经 `north_angle`） |
| `north_angle` | 写入 metrics，便于调试 |
| soft violations | 未满足的 soft OrientationConstraint |

`SiteCoordinateSystem`（`solver/geometry/site_coords.py`）：

```text
model edge (N/S/E/W) → edge_azimuth(north_angle) → world orientation
```

Model：`y=0` = model north，`x=0` = model west（绘图坐标）。  
`preferred_orientation=south` = 世界正南，**不是** SVG 下边界。  
`north_angle=0` 兼容旧行为；`north_angle=90` 时世界南 = model 东边。

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
| `wet_stack_alignment` | WetStack 锚跨层对齐 |
| `wet_zone_alignment` | [deprecated] `wet_stack_alignment` 别名 |

### Site (`evaluation/site.py`)

| Metric | 说明 |
|--------|------|
| `setback_compliance` | 退线合规率 |

## Phase 3 Metrics（建筑评价 MVP）

### Privacy (`evaluation/privacy.py`)

| Metric | 说明 |
|--------|------|
| `privacy_transition_score` | entry→各 private 路径上 category 过渡质量 |
| `private_through_count` | 路径穿过其他 private 的次数 |
| `bad_privacy_transition_count` | 高惩罚过渡步数 |

### Program Fit / Space Efficiency (`evaluation/program_fit.py`)

| Metric | 说明 |
|--------|------|
| `program_coverage` | 程序房间是否都落下 |
| `program_fit` | coverage + area_accuracy |
| `space_efficiency` | compactness × (1 − 0.5×细长比) |

### Circulation（续）

| Metric | 说明 |
|--------|------|
| `reachable_ratio` | RealizedAccessGraph 占用房间可达率 |
| `through_room_count` / `dead_end_count` | 穿堂 / 尽端粗指标 |
| `layout_stability_score` | 1 − repair 扰动 |

**仍后续**：daylight、走廊长度精细化、正式 UI Inspector。

## 与参考原型的关系

`reference/floorplan-generator.html` 的 `computeScore` 实现了：

- 外墙周长效率 = `4×sqrt(面积) / 实际周长 × 100%`
- 长宽比 > 2.2 房间标记
- 湿区 x 对齐消息

Phase 1 将这些逻辑拆分迁移：

- 效率 / 紧凑度 → `geometry.py` / `site.py`
- 长宽比 → `geometry.py` → `aspect_ratio_penalty`
- 湿区对齐 → `vertical.py` → `wet_stack_alignment`（兼容别名 `wet_zone_alignment`）

## Total Score 聚合（Phase 3 默认权重）

```text
total = Σ (score_i × w_i) / Σ w_i

geometry 0.20 | adjacency 0.12 | vertical 0.12 | site 0.08
orientation 0.10 | circulation 0.12 | privacy 0.10
program_fit 0.08 | space_efficiency 0.04 | layout_stability 0.04
```

权重见 `solver/evaluation/weights.py`（`ScoreWeights`）。

## Hard vs Soft

| 类型 | 处理模块 | 结果 |
|------|----------|------|
| Hard constraint 违反 | ConstraintChecker | `valid=False`，不参与正常排名 |
| Soft constraint 违反 | Evaluator | 扣分 + `soft_violations[]` |
| 警告（非约束） | Evaluator | `warnings[]`（如狭长房间） |

## UI 展示（Desktop MVP）

- Candidate Strip：显示 `total_score` 简写（A 91, B 89…）
- Inspector：展开 `explanations` + 各分项 score + metrics + violations
- 失败 candidate：展示 `hard_violations` 详情
- API：`POST /api/generate` 返回 SVG + `DesignScore`

## 状态

- ✅ `DesignScore` / `DesignMetrics` + Phase 3 分项
- ✅ Geometry / Adjacency / Vertical / Site / Orientation / Circulation / Privacy / ProgramFit

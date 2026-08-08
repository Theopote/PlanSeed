# 评分体系

## 设计原则

1. **Evaluator 独立层**：不修改 candidate，只解释质量。
2. **多指标分解**：返回 `DesignScore` 结构，而非单一数字。
3. **Hard / Soft 分离**：Hard 违反在 `ConstraintChecker` 处理；Evaluator 对 soft 约束扣分。

## DesignScore 七轴（用户层）

```python
DesignScore
├── program_score       # 空间清单 / 面积份额 / 邻接
├── spatial_score       # 比例 / 紧凑度 / 形状
├── circulation_score   # 可达 / 深度 / 穿堂 / 死端
├── privacy_score       # 动静分区 / 过渡 / 穿卧
├── environment_score   # 朝向 / 外墙（采光后续）
├── technical_score     # 楼梯 / 湿区 / 入口 / 临路
├── robustness_score    # repair / reslice / 稳定性
├── total_score
├── metrics: DesignMetrics
├── findings: DesignFinding[]
├── explanations[] / warnings[]  # compat：由 findings 派生
└── violations[]
```

| 轴 | 回答的问题 | 底层来源（不重复加权） |
|----|------------|------------------------|
| Program | 房间有没有？面积份额？邻接？ | coverage + area_accuracy + adjacency |
| Spatial | 比例？紧凑？形状？ | aspect/slender + compactness |
| Circulation | 可达？深度？穿堂？ | realized + access intent |
| Privacy | 动静过渡？穿卧？ | privacy path |
| Environment | 朝向？ | orientation（daylight 后续） |
| Technical | 楼梯/湿区/入口/路？ | vertical + site |
| Robustness | 是否靠修补硬撑？ | layout_stability |

### DesignFinding

| 字段 | 说明 |
|------|------|
| `id` | 稳定键，如 `privacy.private_through_room:bed_b` |
| `category` | `program` \| `spatial` \| `circulation` \| …（七轴） |
| `severity` | `info` \| `positive` \| `warning` \| `problem` |
| `title` / `message` | 短标题 + 设计语义说明 |
| `room_ids` | 相关房间 |
| `recommended_action` | 可选改进建议 |

## 第一阶段 Metrics（Phase 1 实现）

### Geometry (`evaluation/geometry.py`)

| Metric | Owner | 说明 |
|--------|------|------|
| `aspect_ratio_penalty` / `slender_room_count` | **spatial** | 房间比例 |
| `area_accuracy` | **program** | 份额一致性 |
| `compactness` | **spatial** | 周长效率（与 slender 同轴但不同子分，轴内合成一次） |

比例与紧凑在 **Spatial** 轴内合成；不与 Program 重复扣面积。

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

| Metric | Owner | 说明 |
|--------|------|------|
| `program_coverage` | **program_fit** | 房间是否都落下 |
| `program_area_accuracy` / `area_accuracy` | **program_fit** | 面积份额（总分只在此计） |
| `compactness` | **space_efficiency** | 外轮廓周长效率 |
| `slender_room_ratio` | geometry（只读） | 不计 space_efficiency 分 |

### Metric Ownership（Phase 3.5）

每个原始 metric **只属于一个 primary score**。其他 evaluator 可引用 metric 写 findings，但不得重复加权进 `total_score`。  
权威表：`solver/evaluation/ownership.py`。

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

## Total Score 聚合（七轴默认权重）

```text
total = Σ (axis_i × w_i) / Σ w_i

program 0.18 | spatial 0.14 | circulation 0.16 | privacy 0.12
environment 0.10 | technical 0.16 | robustness 0.14
```

轴内合成（不再进入 total 二次加权）：
- program = 0.65×fit + 0.35×adjacency
- spatial = 0.55×proportion + 0.45×compactness
- technical = 0.55×vertical + 0.45×site

权重见 `solver/evaluation/weights.py`。

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
- API：`POST /api/generate` 返回 SVG + `design_score`（来自 `LayoutCandidate.evaluation`，不重评）
- `DesignEvaluation` = `DesignScore` 别名；pipeline 写入完整对象，`score` 为 compat 标量

## 状态

- ✅ `DesignScore` / `DesignEvaluation` / `DesignMetrics` + 七轴
- ✅ Geometry / Adjacency / Vertical / Site / Orientation / Circulation / Privacy / ProgramFit
- ✅ Metric Ownership + pipeline 单次评价

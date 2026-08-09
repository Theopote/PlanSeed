# 评分体系

## 设计原则

1. **Evaluator 独立层**：不修改 candidate，只解释质量。
2. **多指标分解**：返回 `DesignScore` 结构，而非单一数字。
3. **Hard / Soft 分离**：Hard 违反在 `ConstraintChecker` 处理；Evaluator 对 soft 约束扣分。

## DesignScore 七轴（用户层）

**冻结（至少两个阶段：3.6–4 / Desktop Alpha v0.1）：** 轴的英文标识与用户显示名不再改动。  
同步冻结 **`DesignScore` / `DesignFinding` 字段契约**（见 [roadmap.md](roadmap.md)#desktop-alpha-v01--契约冻结至少到-v01-发布）；只允许轴内加深 metric 与 ownership，禁止改名或退回 `geometry_score` / `efficiency_score` 等旧并列名。

```text
Program      = Program Fit + Adjacency
Spatial      = Proportion + Compactness
Circulation  = Reachability + Depth + Through-room …
Privacy      = Transition + Through-bedroom …
Environment  = Orientation MVP（朝向 / 外墙；**不含**日照 / 通风 / 景观模拟）
Technical    = Technical Logic = Vertical + Site（楼梯 / 湿区 / 入口·场地；
               **不含**结构 / 设备 / 消防 / 法规 / 施工）
Robustness   = Layout stability / repair
```

**产品文案：** UI / Compare / Finding 必须标明 MVP 范围，避免把 Environment 理解成完整环境性能、把 Technical 理解成全专业技术审查。轴 **标识符**（`environment` / `technical`）仍冻结；显示名可用  
`Environment (Orientation MVP)` / `Technical Logic`。

```python
DesignScore
├── program_score       # 空间清单 / 面积份额 / 邻接
├── spatial_score       # 比例 / 紧凑度 / 形状
├── circulation_score   # 可达 / 深度 / 穿堂 / 死端
├── privacy_score       # 动静分区 / 过渡 / 穿卧
├── environment_score   # Orientation MVP：朝向 / 外墙
├── technical_score     # Technical Logic：楼梯 / 湿区 / 入口·场地
├── robustness_score    # repair / reslice / 稳定性
├── total_score
├── metrics: DesignMetrics
├── findings: DesignFinding[]
├── explanations[] / warnings[]  # compat：由 findings 派生
└── violations[]
```

| 轴（冻结名） | 回答的问题 | 底层来源（不重复加权） | MVP 边界 |
|----|------------|------------------------|----------|
| Program | 房间有没有？面积份额？邻接？ | Program Fit + Adjacency | — |
| Spatial | 比例？紧凑？形状？ | Proportion + Compactness | — |
| Circulation | 可达？深度？穿堂？ | realized + access intent | — |
| Privacy | 动静过渡？穿卧？ | privacy path | — |
| Environment | 朝向 / 外墙？ | orientation | **非**日照/通风/景观模拟 |
| Technical | 楼梯/湿区/入口/场地？ | Vertical + Site | **非**结构/设备/消防/法规 |
| Robustness | 是否靠修补硬撑？ | layout_stability | — |

### DesignFinding

| 字段 | 说明 |
|------|------|
| `id` | 稳定键，如 `privacy.private_through_room:bed_b` |
| `category` | `program` \| `spatial` \| `circulation` \| …（七轴） |
| `severity` | `info` \| `positive` \| `warning` \| `problem` |
| `title` / `message` | 短标题 + 设计语义说明 |
| `room_ids` | 相关房间 |
| `recommended_action` | 可选改进建议 |

#### design heuristic ≠ code compliance

Finding / Inspector 文案必须保持 **设计启发式**，与 **规范合规** 严格分开。

| 允许（启发式） | 禁止（无 CodeProfile 时） |
|----------------|---------------------------|
| 有利于管井与施工组织 | 符合规范 / 合法 |
| 朝向偏好满足、私密过渡更好 | 满足消防 / 满足无障碍 |
| 未提供退界 → 信息缺失提示 | 退线「合规通过」 |

在具备 `CodeProfile` / `Jurisdiction` / `Rule source` 之前，**不要**把 Finding 写成审查结论。  
内部 metric 名 `setback_compliance` 仅表示 buildable 落位比例，对外文案勿称「规范合规率」。


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

`rank_candidates` Alpha 默认：

```text
rank_mode = "axis"                 # score + 轴叙事 + 几何 diversity
min_diversity_threshold = 0.85
selection_version = axis-diversity-v1
```

贪心选取 Top K：优先最高总分，再选轴优势替代方案，并用 `layout_similarity` 去重。  
`rank_mode="pareto"` 为 **Experimental**（非默认；`pareto-top1-axes-v2`：slot1=最高总分，目标复用七轴语言）。  
`min_diversity_threshold=None` → 纯分数。  
配置：`SolverConfig.rank_mode` / `min_diversity_threshold`。详见 [phases/phase-8.5-alpha-stabilization.md](phases/phase-8.5-alpha-stabilization.md)。

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
| `setback_compliance` | 程序房间落在 buildable 内比例（内部名含 compliance，**非**法规结论） |
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

### Site（文案注意）

对外勿把 `setback_compliance` 说成「退线合规率」；称 **buildable 落位比例** 即可。


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
- `design_score.evaluation_version` + 响应 `solver_identity`（见下）
- `DesignEvaluation`：**temporary compatibility alias** → 目前 `= DesignScore`（同构，避免双源）；pipeline 写入完整对象，`score` 为 compat 标量

## 版本签名（regression / 历史结果）

常量集中在 [`packages/schema/identity.py`](../packages/schema/identity.py)：

| 字段 | 当前值 | 含义 |
|------|--------|------|
| `solver_version` | `0.5` | Solver 管线总签名（含 Solver 2.0 能力面；默认语义见 selection） |
| `generator_strategy` | `guillotine` | 生成策略（`maxrect` 等为 opt-in） |
| `generator_version` | `guillotine-lock-v4` | 当前主生成器规则包 |
| `selection_strategy` | `axis-diverse` | Alpha 默认 Top-K 策略 |
| `selection_version` | `axis-diversity-v1` | 选优规则包；Pareto Experimental=`pareto-top1-axes-v2` |
| `evaluation_version` | `residential-alpha-v1` | 七轴权重 / Finding 规则包 |
| `assignment_strategy` | `heuristic` | 楼层归属；`cpsat` 为 research |
| `geometry_backend` | `rect` | 默认矩形；不规则场地意图=`shapely-orthogonal` |

完整模型：`SolverProvenance`（`packages/schema/provenance.py`）。

持久化示例：

```json
{
  "solver_version": "0.5",
  "generator_strategy": "guillotine",
  "generator_version": "guillotine-lock-v4",
  "selection_strategy": "axis-diverse",
  "selection_version": "axis-diversity-v1",
  "evaluation_version": "residential-alpha-v1",
  "assignment_strategy": "heuristic",
  "geometry_backend": "rect",
  "total_score": 87.2
}
```

**何时 bump：** 改权重、轴合成、Finding 规则 → 升 `evaluation_version`；改生成拓扑 → 升 `generator_version`；换默认 strategy → 升对应 `*_strategy` 记录并由 `selection_version` / `solver_version` 可追踪；改 Top-K / ranking / compare 默认对象 → 升 **`selection_version`**（及必要时 `solver_version`）；大管线变更 → 升 `solver_version`。  
否则「同几何明日分数变了 / Top-1 换人了」无法解释。`engine_version`（health）仍是进程/打包身份，与算法签名分开。

### DesignEvaluation vs DesignScore（非 P0，schema 稳定后再拆）

| 现在 | 长期目标 |
|------|----------|
| `DesignEvaluation = DesignScore` | `DesignEvaluation` 为真正模型 |

Score 与 Evaluation 语义不同：前者是七轴分数载体；后者是一次评价事件/结果包。稳定后建议：

```text
DesignEvaluation
  score: DesignScore          # 含 evaluation_version（现已在 alias 上）
  findings / metrics / profile
  # 候选：timestamp / metric_ownership_version / scenario / comparison_signature
```

拆分前业务层继续把 `LayoutCandidate.evaluation` 当完整评价对象用；**不要**再引入第二套并行类型。

## 状态

- ✅ `DesignScore` / `DesignEvaluation`（alias）/ `DesignMetrics` + 七轴
- ✅ `evaluation_version` + `solver_identity`（`packages/schema/identity.py`）
- ⬜ `DesignEvaluation` 真正模型化（temporary alias → 组合模型；非 P0）
- ✅ Geometry / Adjacency / Vertical / Site / Orientation / Circulation / Privacy / ProgramFit
- ✅ Metric Ownership + pipeline 单次评价

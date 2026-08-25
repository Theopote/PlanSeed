# PlanSeed Design Benchmark v2

> **代号：** `design-benchmark-v2` / Suite `design-v2`  
> **版本：** v2.0-spec（2026-08-26）  
> **状态：** Specification — harness 待实现（v0.2-A）  
> **命名注意：** 本 benchmark **不是** Phase 6.7 的 Parser Benchmark v2（relations / floor_preferences）。  
> 后者测 NL→RequirementSpec；本 benchmark 测 **DesignProgram→LayoutCandidate 的设计可接受性**。

## 1. 定位

Design Benchmark v2 回答一个问题：

> **建筑师是否愿意在这个生成结果上继续深化设计？**

它不是 generator 资格判定（那是 [Layout Benchmark Suite v1](baselines/layout-benchmark-suite-v1.md) 的职责），  
也不是 parser 准确率（那是 `packages/llm/benchmark/` 的职责）。

### 与 Suite v1 的关系

| 维度 | Suite v1（qualification） | Design Benchmark v2（acceptance） |
|------|---------------------------|-----------------------------------|
| 目的 | Guillotine vs MaxRect 策略比较 | 设计质量与用户可接受性 |
| 案例数 | 12（B01–B12） | 20（B01–B20，**独立编号空间**） |
| 主指标 | `valid_rate`、策略 gate | **A/B 级候选出现率**（`ab_rate`） |
| 评级 | 无人工 grade | A/B/C/D architect acceptance |
| 场地 | 矩形为主 | 矩形 + 不规则正交 + 高退界 |
| 策略 | Guillotine + MaxRect 对比 | **Guillotine 为主**（Alpha 默认） |

Suite v1 **保留**，继续服务 Experimental Lab 与 MaxRect gate。  
Suite v2 部分 case 可复用 v1 的 `DesignProgram` builder（见附录 A），但评价维度与 gate 完全不同。

---

## 2. 主指标

### 2.1 `ab_rate`（Primary）

```text
ab_rate(case, strategy) = (count_A + count_B) / candidates_generated
```

- 对每个 case 生成 `N` 个 candidate（默认 `N=32`，与 Suite v1 一致便于对比）
- 仅统计 **hard-constraint valid** 的 candidate 参与评级（invalid 记为自动 D）
- 跨 case 汇总：`ab_rate_aggregate = mean(ab_rate per case)`（**不得**只看 aggregate 忽略单 case 劣化）

### 2.2 辅指标（Automatic）

每个 valid candidate 自动记录：

| 字段 | 来源 |
|------|------|
| 七轴分 | `DesignScore`（[scoring.md](scoring.md)） |
| `DesignFinding[]` | Evaluator |
| `valid` | `ConstraintChecker` |
| `connection_repairs` | Robustness |
| `layout_fingerprint` | 几何去重 |

### 2.3 目标（初版基线，待首跑校准）

首跑前不设 hard gate；首跑后建立 baseline JSON，再定：

- `ab_rate_aggregate ≥ TBD`（建议首目标 0.15–0.25，视 valid_rate 校准）
- 单 case `ab_rate` 不得 < 0.05（防「平均好看、个别完全不可用」）
- Core cases（B01–B07）`ab_rate` 优先于 Site cases（B08–B12）

---

## 3. 评价维度

每个 case 的每个 valid candidate 记录以下 11 个维度。  
前 10 个由自动指标 **代理**（proxy）；第 11 个为 **人工评级**。

| # | 维度 | 自动代理（DesignScore / Metrics） | 人工评审要点 |
|---|------|-----------------------------------|--------------|
| 1 | Program satisfaction | `program_score`, `required_adjacency_satisfaction` | 房间是否齐全、面积份额是否合理 |
| 2 | Topology quality | `topology_plan` 一致性、zone 连贯性（**待新 KPI**） | 公私分区是否清晰、功能块是否成组 |
| 3 | Circulation | `circulation_score`, `reachable_ratio`, `private_through` finding | 动线是否自然、有无穿堂/死端 |
| 4 | Privacy | `privacy_score`, `privacy.private_through_room` | 卧室是否被公共动线穿越 |
| 5 | Room proportion | `spatial_score`, `aspect_ratio_penalty`, `slender_room_count` | 房间形状是否可用（非极端狭长） |
| 6 | Daylight potential | `environment_score`, orientation satisfaction | 主要房间是否有外墙、朝向是否合理 |
| 7 | Facade opportunity | exterior room count per orientation（**待增强**） | 立面是否有机会开窗、入口是否合理 |
| 8 | Structural regularity | `technical_score`, `wet_stack_alignment` | 湿区是否可堆叠、结构是否过于碎 |
| 9 | Furniture usability | **TBD**（v0.2-A 标为 manual-only） | 主要家具是否摆得下（人工判断） |
| 10 | Site relationship | `setback_compliance`, `entry_on_road`, `garage_on_road` | 建筑与场地、道路、庭院关系 |
| 11 | **Architect acceptance** | — | **A / B / C / D**（见 §4） |

自动 proxy 用于 **预筛与相关性分析**；最终 gate 以 `ab_rate` 为准。

---

## 4. Architect Acceptance 评级

| Grade | 含义 | 后续动作 |
|-------|------|----------|
| **A** | 基本可以继续深化 | 可直接进入局部编辑 / 导出深化 |
| **B** | 可以修改后继续 | 值得 lock + partial regen |
| **C** | 只能作为构思参考 | 保留拓扑思路，几何需大改 |
| **D** | 明显不可用 | 丢弃；分析 failure pattern |

### 评级规则

1. **Invalid candidate**（hard violation）自动记 **D**，不参与 `ab_rate` 分子。
2. 人工评级时参考自动 proxy，但 **不以总分为唯一依据**（88 分仍可能是 D）。
3. 每个 case 附 **D 级典型特征** checklist（见 §5），评审时勾选。
4. 首版评级工具：JSON 文件或 spreadsheet；v0.2-A 后期可加 Desktop 评级面板。

### 评审人数

- 首跑校准：**≥1 名有住宅设计经验评审者**
- 正式 baseline：**≥2 人**，分歧取较低 grade

---

## 5. 案例目录（B01–B20）

### 分层

| 层级 | Case | 覆盖 |
|------|------|------|
| **Core** | B01–B07 | 典型矩形独栋程序 |
| **Site** | B08–B12 | 场地形态与退界 |
| **Intent** | B13–B20 | 设计意图与程序张力 |

---

### B01 — 8m × 12m 城市窄宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 8×12 m；`road_edges=[south]`；`entrance_edge=south` |
| 层数 | 1F |
| 程序 | 客厅 16㎡、厨房 9㎡、卫 4㎡、主卧 12㎡、次卧 10㎡ |
| 约束 | 客厅朝南（soft）；厨房邻餐厅区（soft） |
| 设计意图 | 窄面宽城市宅，公共区紧凑、卧室靠内 |
| 关注指标 | spatial, circulation, room proportion |
| D 级特征 | 卧室面宽 < 2.4m；客厅无外墙；厨卫无法相邻 |
| Suite v1 | 近似 B01（8×10），尺寸与程序略扩 |

---

### B02 — 12m × 15m 普通独栋

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 12×15 m；南向道路 |
| 层数 | 2F |
| 程序 | F1：客厅 24、餐厨 18、客卫 4、车库 20；F2：主卧 18+主卫 5、次卧×2 各 12、公卫 4 |
| 约束 | 车库临道路（soft）；主卧朝南（soft） |
| 设计意图 | 标准郊区独栋，公私分层清晰 |
| 关注指标 | program, privacy, technical（湿区堆叠） |
| D 级特征 | 二层卧室无独立可达；车库入口背路；公区过碎 |
| Suite v1 | 近似 B04（12×16+车库） |

---

### B03 — 南向庭院住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 14×16 m；**南侧留庭院**（`setbacks.south=4` 或 courtyard hole） |
| 层数 | 2F |
| 程序 | F1：客厅 26、餐厅 14、厨房 12、门厅 6；F2：主卧 18、次卧×2、卫生间×2 |
| 约束 | 客厅/主卧视觉连接庭院（soft, `visual_connection`）；厨房避免正对主卧（soft separation） |
| 设计意图 | 生活空间围绕南向庭院组织 |
| 关注指标 | environment, site relationship, privacy |
| D 级特征 | 主要房间背庭院；庭院被服务空间占据 |
| Suite v1 | 无直接对应；可复用 `_two_floor_base` 改 site |

---

### B04 — 双车库住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 14×18 m；道路在西侧 |
| 层数 | 2F |
| 程序 | F1：车库×2 各 18㎡、门厅 8、洗衣 5；F2：起居 28、厨房 14、卧室×3、卫生间×2 |
| 约束 | 双车库均临道路（soft）；车库与门厅相邻（soft） |
| 设计意图 | 双车家庭，车库区与服务区成组 |
| 关注指标 | program, site relationship, circulation |
| D 级特征 | 车库无法并排或入口冲突；起居区被车库挤压变形 |
| Suite v1 | 扩展 B04 |

---

### B05 — 三代同堂

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 13×16 m |
| 层数 | 2F（**老人套房在一层**） |
| 程序 | F1：客厅 22、餐厅 14、厨房 12、**老人卧 14+老人卫 5**、客卫 4；F2：主卧 18+主卫 5、次卧×2、公卫 4、书房 10 |
| 约束 | 老人卧远离厨房噪音（separation soft）；老人卧一层（hard floor assignment） |
| 设计意图 | 多代分层，老人无障碍动线 |
| 关注指标 | circulation, privacy, program |
| D 级特征 | 老人卧在二层；公区动线穿越老人卧；无一层卫生间 |
| Suite v1 | 无 |

---

### B06 — 一层适老住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 12×14 m；单层 |
| 层数 | 1F only |
| 程序 | 客厅 22、餐厨 16、主卧 16、次卧 12、卫生间×2（含无障碍主卫 6㎡）、洗衣 5、储藏 4 |
| 约束 | 主卧近卫生间（adjacency soft）；无台阶（单层 hard）；走廊宽度偏好（circulation soft） |
| 设计意图 | 全龄一层，动线短、无垂直交通 |
| 关注指标 | circulation, room proportion, furniture usability |
| D 级特征 | 狭长走廊；卫生间不可达；房间极端狭长 |
| Suite v1 | 扩展 B02 |

---

### B07 — 两层四卧住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 11×14 m |
| 层数 | 2F |
| 程序 | F1：客厅 24、餐厨 16、客卫 4；F2：主卧 16+主卫 5、次卧×3 各 11、公卫 4 |
| 约束 | 四卧均在二层（hard）；楼梯位置居中（soft） |
| 设计意图 | 典型四卧家庭，二层私密区完整 |
| 关注指标 | program, privacy, technical |
| D 级特征 | 次卧数不足；一层出现卧室；楼梯占满核心区 |
| Suite v1 | 近似 B03 |

---

### B08 — 狭长地块

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 **9×20 m**（面宽 9m） |
| 层数 | 2F |
| 程序 | 标准两层三卧（同 B07 缩减） |
| 约束 | 无 |
| 设计意图 | 窄面宽极限下的可用布局 |
| 关注指标 | spatial, circulation, room proportion |
| D 级特征 | 大量房间面宽 < 2.4m；无自然采光面；动线折返过多 |
| Suite v1 | **等同 B05**（可直接复用 program） |

---

### B09 — L 型场地

| 字段 | 定义 |
|------|------|
| 场地 | L 型正交多边形（参考 `test_irregular_site._l_shape`：10×10 缺 NE 5×5，可建 75㎡） |
| 层数 | 2F |
| 程序 | 紧凑两层三卧 |
| 约束 | `geometry_backend=shapely`（experimental）；建筑落在 buildable 内（hard） |
| 设计意图 | L 型用地高效利用凹角 |
| 关注指标 | site relationship, spatial, technical |
| D 级特征 | 房间越出 buildable；凹角空间浪费；翼间动线断裂 |
| Suite v1 | 无（需 irregular site） |

---

### B10 — 转角地块

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 12×12 m；**道路在南+东**（`road_edges=[south,east]`） |
| 层数 | 2F |
| 程序 | 标准两层三卧 + 车库 18 |
| 约束 | 入口可临南或东（soft）；车库优先临道路（soft） |
| 设计意图 | 转角用地入口与车库灵活布置 |
| 关注指标 | site relationship, circulation |
| D 级特征 | 入口背路；车库无法到达；两面临街房间私密性差 |
| Suite v1 | 无 |

---

### B11 — 不规则正交场地

| 字段 | 定义 |
|------|------|
| 场地 | 阶梯形正交多边形（≥6 顶点，如 14×10 带 4×3 凸出） |
| 层数 | 2F |
| 程序 | 标准两层三卧 |
| 约束 | Shapely buildable；全部 program rooms 在 buildable 内 |
| 设计意图 | 非矩形用地的基础可行性 |
| 关注指标 | site relationship, technical, spatial |
| D 级特征 | 建筑轮廓锯齿无逻辑；大量房间在凹角不可用地 |
| Suite v1 | 无 |

---

### B12 — 高退界限制

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 14×16 m；`setbacks: N=3, S=2, E=2, W=2`（`setback_source=user`） |
| 层数 | 2F |
| 程序 | 标准两层三卧 + 车库 |
| 约束 | 退界内建造（hard via buildable）；车库临道路 |
| 设计意图 | 退界压缩下的紧凑布局 |
| 关注指标 | site relationship, program, spatial |
| D 级特征 | 房间越界；可建区利用率极低导致房间畸形 |
| Suite v1 | 无 |

---

### B13 — 主卧套房优先

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 11×14 m |
| 层数 | 2F |
| 程序 | 主卧 20㎡ + 主卫 6㎡ + 衣帽间 5㎡（F2）；标准公区 F1 |
| 约束 | 主卧+主卫+衣帽间成组（adjacency hard soft）；主卧远离入口（separation soft） |
| 设计意图 | 套房完整性优先于次卧面积 |
| 关注指标 | program, privacy, topology quality |
| D 级特征 | 主卫不与主卧相邻；衣帽间被公共区挤压；套房被切碎 |
| Suite v1 | 无 |

---

### B14 — 客餐厨开放式

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 12×14 m |
| 层数 | 1F（或 2F 公区一层） |
| 程序 | 客厅 28、餐厅 14、厨房 12、卧室×2、卫生间×2 |
| 约束 | living–dining–kitchen 连续邻接（adjacency soft, 高权重） |
| 设计意图 | 开放起居餐厨一体化 |
| 关注指标 | program, topology quality, circulation |
| D 级特征 | 厨房与客厅被走廊隔开；餐厨不连通；开放区被楼梯切断 |
| Suite v1 | **等同 B09** |

---

### B15 — 强私密性需求

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 11×13 m |
| 层数 | 2F |
| 程序 | 标准两层三卧 |
| 约束 | 主卧与客厅 separation ≥4m（soft）；次卧与厨房 separation ≥3m；主卧朝南（soft） |
| 设计意图 | 高私密性家庭，公私彻底分离 |
| 关注指标 | privacy, circulation, topology quality |
| D 级特征 | 公区动线穿主卧；卧室门开向客厅；私密区与入口无过渡 |
| Suite v1 | **等同 B08** |

---

### B16 — 工作室+住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 10×16 m |
| 层数 | 2F |
| 程序 | F1：**工作室 20**、门厅 6、客卫 4；F2：起居 22、厨房 12、主卧 16、次卧 11 |
| 约束 | 工作室独立入口（soft, 第二 exterior entry）；工作室与卧室区 separation（soft） |
| 设计意图 | 居家办公，工作区与生活区可分离 |
| 关注指标 | program, privacy, site relationship |
| D 级特征 | 工作室与卧室共用动线无隔离；无独立工作区入口 |
| Suite v1 | 无 |

---

### B17 — 多入口住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 13×15 m；道路在南 |
| 层数 | 2F |
| 程序 | 主入口+**侧入口**（服务入口）；车库、厨房、门厅 |
| 约束 | 厨房可近侧入口（soft）；主入口进玄关/客厅（soft） |
| 设计意图 | 主客分流、送货动线独立 |
| 关注指标 | circulation, site relationship |
| D 级特征 | 仅单一入口；服务动线穿越客厅 |
| Suite v1 | 无 |

---

### B18 — 大庭院住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 18×20 m；**中央庭院**（courtyard hole 4×4，参考 `test_irregular_site._courtyard`） |
| 层数 | 2F |
| 程序 | 起居环绕庭院；卧室二层 |
| 约束 | 客厅视觉连接庭院（soft）；厨房避免正对卧室门（soft） |
| 设计意图 | 庭院为核心组织空间 |
| 关注指标 | environment, site relationship, topology quality |
| D 级特征 | 庭院被楼梯/走廊占满；主要房间背庭院 |
| Suite v1 | 无 |

---

### B19 — 极小住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 **7×9 m**（63㎡ 用地） |
| 层数 | 1F |
| 程序 | 客厅 14、厨房 7、卫 3.5、卧 10（**总计 ≈34㎡ 功能面积**） |
| 约束 | 无多余房间；紧凑布局 |
| 设计意图 | 极小用地极限可行性 |
| 关注指标 | spatial, program, furniture usability |
| D 级特征 | 房间不可使用；无卫生间；功能面积分配失衡 |
| Suite v1 | 比 B01 更小 |

---

### B20 — 高面积利用率住宅

| 字段 | 定义 |
|------|------|
| 场地 | 矩形 10×12 m |
| 层数 | 2F |
| 程序 | **满铺**：每层尽量填满，房间数偏多（3卧2卫+储藏+洗衣） |
| 约束 | 最小走廊（soft）；无大面积浪费 |
| 设计意图 | 经济型高利用率布局 |
| 关注指标 | spatial, circulation, program |
| D 级特征 | 为凑面积产生极端狭长房间；无走廊导致动线穿房间 |
| Suite v1 | 无 |

---

## 6. 评级工作流

```text
1. 生成
   uv run python -m solver.benchmark --suite design-v2 --count 32 --strategy guillotine

2. 导出
   每 candidate：SVG + DesignScore JSON + DesignFinding 摘要

3. 人工评级
   评审者填写 grades.json（per case × candidate_index × grade）

4. 汇总
   计算 ab_rate、failure pattern、自动 proxy 与 grade 的相关性

5. 基线
   写入 docs/baselines/design_benchmark_v2_n32.json
```

### grades.json 格式（草案）

```json
{
  "suite": "design-benchmark-v2",
  "suite_version": "v2",
  "candidate_count": 32,
  "reviewer": "architect-01",
  "reviewed_at": "2026-08-26",
  "grades": {
    "B01": {
      "0": {"grade": "B", "notes": "客厅偏窄但可改"},
      "1": {"grade": "D", "notes": "卧室面宽不足", "d_checklist": ["slender_room"]}
    }
  }
}
```

---

## 7. Harness 规格（v0.2-A 实现）

### 文件布局（计划）

```text
solver/fixtures/design_suite_v2.py      # B01–B20 case builders
solver/benchmark/design_acceptance.py   # 评级汇总 + ab_rate
docs/baselines/design_benchmark_v2_*.json
```

### CLI（计划）

```bash
uv run python -m solver.benchmark --suite design-v2 --count 32
uv run python -m solver.benchmark --suite design-v2 --cases B01,B08 --count 8
uv run python -m solver.benchmark --suite design-v2 --export-svg debug/benchmark-v2/
uv run python -m solver.benchmark --suite design-v2 --merge-grades grades.json
```

### 实现顺序

1. **Wave 1（Core B01–B07）** — 矩形场地，复用 Suite v1 builders
2. **Wave 2（Intent B13–B20）** — 约束张力 case
3. **Wave 3（Site B08–B12）** — 需 `geometry_backend=shapely` experimental

---

## 8. 基线与 Gate

首跑前 **不设 gate**。首跑后：

1. 记录 Guillotine `ab_rate` per case 为 baseline
2. 分析 D 级 failure pattern → 反馈 solver / evaluator / topology
3. v0.2-B（Partial Regen）完成后，增加 **regen case**（从 B 级方案 lock 后局部重生成，测 ab_rate 提升）

---

## 附录 A — Suite v1 复用映射

| Design v2 | Suite v1 | 关系 |
|-----------|----------|------|
| B08 | B05 | 直接复用 program |
| B14 | B09 | 直接复用 program |
| B15 | B08 | 直接复用 program |
| B01 | B01 | 近似，尺寸 8×12 vs 8×10 |
| B02 | B04 | 近似，尺寸 12×15 vs 12×16 |
| B07 | B03 | 近似 |

## 附录 B — 与 v0.2 里程碑关系

| 里程碑 | 依赖本 benchmark |
|--------|------------------|
| v0.2-A | 本文件即为交付物之一 |
| v0.2-B Partial Regen | 需 B 级方案作 regen 输入 |
| v0.2-C Topology | topology quality KPI 在本 benchmark 验证 |
| v0.2-D Site Editor | Site cases B09–B12 需 UI 完成后重跑 |

详见 [v0.2-architect-workflow.md](v0.2-architect-workflow.md)。

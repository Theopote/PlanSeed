# PlanSeed 路线图

> **当前焦点：Phase 3.5 — Core Consolidation & Local Desktop Runtime**  
> 详案：[phase-3.5-core-consolidation.md](phase-3.5-core-consolidation.md)  
> 停止扩 solver / 不上 Ollama。收口评价链 + **本地独立运行** → Desktop Alpha。

## 阶段总览（以代码为准）

| Phase | 主题 | 状态 |
|-------|------|------|
| 0–2.3 | Architecture → Realized Circulation | ✅ |
| **3** | **Architectural Evaluation** | **✅ MVP** |
| **3.5** | **Core Consolidation & Local Desktop Runtime** | **← 当前** |
| **4** | **Desktop Workbench（加深 / 交互）** | **🟡 壳已有**；结构锁定，本阶段只加深不重做 |
| **5** | **Packaging 硬化**（CSP、签名、跨平台 sidecar） | 未开始（Alpha 后门禁） |
| **6** | **Local LLM** | **未开始**（P2；晚于 Compare） |
| 7–8 | Interactive Editing / Persistence | 未开始 |
| — | SVG Debug | ✅ 开发工具 |

**禁止：** 因 UI 已出现就堆按钮；推倒四区工作台；把 LLM 插队到 Compare / Sidecar 之前。

---

## Phase 3 — Architectural Evaluation（✅ MVP）

Evaluator 只评分，不改几何。用户层七轴：

| 用户轴 | 模块 | 要点 |
|--------|------|------|
| Program | `program_fit.py` + adjacency | 清单覆盖 / 面积份额 / 邻接 |
| Spatial | geometry + compactness | 比例 / 紧凑度（面积归 Program） |
| Circulation | `circulation.py` + `access.py` | realized 可达 / 深度 / 穿堂 |
| Privacy | `privacy.py` | entry→private 过渡；穿卧惩罚 |
| Environment | `orientation.py` | 朝向 / 外墙；采光后续 |
| Technical | `vertical.py` + entry/site | 楼梯 / 湿区 / 入口 / 临路 |
| Robustness | repair metrics | ConnectionResolver / reslice 稳定性 |

`DesignScore` / `DesignEvaluation`：七轴 + `findings[]`；`explanations` / `warnings` 由 findings 派生。  
**不做（本 Phase）**：daylight；LLM；房间拖拽编辑。

---

## Phase 3.5 — Core Consolidation & Local Desktop Runtime（← 当前）

详案：[phase-3.5-core-consolidation.md](phase-3.5-core-consolidation.md)

### 优先级

| 级 | 主题 | 状态 |
|----|------|------|
| **P0** | DesignEvaluation / Finding、Metric ownership、去重评、roadmap | ✅ |
| **P0** | **Tauri sidecar runtime**（本地独立工具能否成立） | 🟡 骨架；**Windows 真装包未验收** |
| **P1** | API layering | ✅ |
| **P1** | Inspector findings 加深 + **Candidate Compare（A vs B）** | 🟡 / ✅ Compare MVP |
| **P2** | Rejected Candidates（为何被淘汰） | 规划 |
| **P2** | Local LLM | **不做本阶段** |

### Desktop Alpha 里程碑（本阶段完成定义）

```text
双击 PlanSeed → 后台自动起引擎 → 输入需求 → Generate
→ Top 5 → 评分与设计解释 → A/B 比较
```

跑通即第一个真正可用 Desktop Alpha。  
解释必须 deterministic（findings / score 差分），禁止用 LLM 写优缺点。

### Candidate Compare（P1）

不只点击切换 A…E；支持 **Compare A vs B**：七轴对照表 + 双方优势列表（由 findings/分数差分生成）。

### Rejected Candidates（后续）

开发模式展示未入选 / invalid：`seed` + hard violations / core failure / 缺失开口等。  
让系统显得「有判断依据」，而非随机吐方案。

---

## Phase 4 — Desktop Workbench（🟡 壳；结构锁定）

**围绕加深，禁止推倒重做。** UI = 观察/控制 solver 的窗口，不是功能堆场。

```text
┌ Requirements ┬──────── Floorplan ────────┬ Inspector ┐
│ Site         │                           │ Score     │
│ Program      │        FLOOR PLAN         │ Findings  │
│ Constraints  │                           │ Metrics   │
│ Preferences  │                           │ Rooms     │
└──────────────┴───────────────────────────┴───────────┘
│                   Candidate Strip（含 Compare）       │
└─────────────────────────────────────────────────────┘
```

- [x] 四区壳 + `pnpm dev` + 引擎就绪文案  
- [ ] Compare / Rejected / Constraints·Preferences 分区 → 在 **3.5 / 本 Phase 加深**，不另起布局  

开发工具：`uv run python -m solver.visualize`。

---

## Phase 5 — Packaging 硬化（Alpha 后）

- [ ] 跨平台 sidecar 验收  
- [ ] **收紧 `csp`**（开发期 `null` 可接受；正式包禁止长期保持）  
- [ ] 安装包签名 / 分发（按需）

---

## Phase 6 — Local LLM（未开始）

```text
Natural Language → (Ollama) → RequirementSpec → normalize → Solver
```

禁止 LLM 输出坐标 / SVG / DesignProgram。**晚于 Desktop Alpha 与 Compare。**

---

## Phase 7+（未开始）

- **7** Interactive Editing（拖拽等；仍在中栏 Floorplan）  
- **8** Persistence / Projects

---

# 历史阶段（已完成，供查阅）

以下 Phase 0–2.x 已收口；**不要**当作当前开发焦点。

## Phase 1.5 — Solver Reliability（✅）

### P0 Correctness（✅ 已完成）

- [x] Hard adjacency checker
- [x] Soft area/width → `ConstraintEvaluationResult` 不丢弃
- [x] Missing / duplicate / wrong_floor / unknown room（`geometry.*`）
- [x] Duplicate room assignment detection
- [x] Floor assignment consistency
- [x] RequirementSpec assumption / unknown tracking（空 spaces ≠ benchmark）
- [x] Orientation evaluator 闭环
- [x] Exterior edges / wall length
- [x] LayoutSignature + buildable 归一化 similarity
- [x] `docs/constraint-coverage.md`
- [x] Quality regression 门槛 + demo 指标
- [x] SVG debug（room id / target·actual area）

### P1 Floor Assignment（✅）

```text
Rooms → FloorAssignmentSolver → floor.room_ids
```

Generator 不猜楼层。

**语义边界：** 住宅规则以 `RoomSpec.tags` 为准；`name` 是 UI 文本。  
中文 name 子串回退冻结在 `solver/semantics/roles.py`。  
自然语言 → tags 由 normalize / Phase 6 LLM 负责；Solver 不承担 NLP。

### P2 StairCore（✅；禁止缩小）

```text
1.6×整进深条带  →  StairCore ~1.8×4.2，N/S/E/W/center
放不下 → 换 orientation / placement → 仍不行 → geometry.core_unfit（不缩放）
```

### P3 Architectural Zones（✅ 初版）

```text
building envelope → StairCore → Zones (day / night / service) → Rooms
```

`ZonePlanner`：功能区与 `WetStack` 分离；MVP `max_wet_stacks=1`。

---

## 目标生成流水线（Phase 2 终态，✅）

```text
DesignProgram
      ↓
FloorAssignment
      ↓
Semantic RoomGraph
      ↓
AccessGraph
      ↓
ZonePlanner
      ↓
CorePlacement
      ↓
Graph-aware Room Ordering
      ↓
Guillotine
      ↓
ConnectionResolver
      ↓
DoorPlacement
      ↓
AccessibilityValidator
      ↓
Evaluator（→ LayoutCandidate.evaluation）
```

### Graph 反向驱动 Generator（已完成）

| 阶段 | 行为 |
|------|------|
| ~~纯 `rng.shuffle(rooms)`~~ | ❌ 已淘汰 |
| **2.0 ✅** | `TopologyPlan.pack_order_hint` + adjacency cluster 连续序 |
| **2.0.1 ✅** | `[Kitchen,Dining,Living]` 同一 slicing group |
| **2.1 ✅** | AccessGraph + ConnectionResolver 局部修补 |
| **2.1.2–2.1.3 ✅** | 跨区重切 / 绕核多 free-rect |
| **当前主线** | Phase 3.5 Core Consolidation → Desktop Alpha（sidecar + Compare） |

---

## Phase 2.0 — Topology-driven pack（✅ MVP）

```text
RoomGraph → TopologyPlan → Zone placement → Room placement
```

- `TopologyPlanner` 产出簇与 `pack_order_hint`
- Guillotine 区内序读 TopologyPlan；邻接簇为 slicing group

## Phase 2.1 — AccessGraph（✅）

```text
Room topology → AccessGraph → Required connections → Shared boundary → Door placement
```

- `ExteriorEntry`、`access.unreachable_room`、默认 soft AccessGraph
- ConnectionResolver：缝隙修补 → 局部重切 → 绕核多 free-rect
- **仍不**整层为连通重跑 Guillotine

## Phase 2.3 — Realized Circulation（✅）

```text
Adjacency / 共墙  ≠  Access Intent  ≠  Realized Access
```

- Reachability 只走 `RealizedAccessGraph`
- `RepairRecord` + repair budget；`layout_stability`

## Phase 2.2 — Door polish（✅；不回改房间）

- 净宽 soft、`swing_room_id`、铰链、SVG 门扇弧
- 无共边禁止凭空戳门

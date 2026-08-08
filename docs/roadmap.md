# PlanSeed 路线图

> **当前焦点：Phase 3.5 — Evaluation Consolidation**  
> Solver / 拓扑 / Phase 3 评价 MVP 已就绪；Desktop 为可用壳，**Local Runtime / Sidecar 尚未闭环**。

## 阶段总览（以代码为准）

| Phase | 主题 | 状态 |
|-------|------|------|
| 0 | Architecture Foundation | ✅ |
| 1 | Deterministic Layout Core | ✅ |
| 1.5 | Solver Reliability | ✅ |
| 1.6 | Spatial Semantics Hardening | ✅ |
| 2.0–2.3 | Topology / Access / Doors / Realized Circulation | ✅ |
| **3** | **Architectural Evaluation** | **✅ MVP**（七轴 + findings） |
| **3.5** | **Evaluation Consolidation** | **← 当前**（Ownership、去重评、`evaluation` 挂候选、API 拆分） |
| **4** | **Desktop Workbench** | **🟡 MVP**（四区壳 + `pnpm dev`；非独立安装包） |
| **5** | **Local Runtime / Sidecar / Packaging** | **未完成**（骨架有；装包 / CSP / 零 Python 未验收） |
| **6** | **Local LLM**（Ollama → RequirementSpec） | **未开始** |
| 7 | Interactive Editing | 未开始 |
| 8 | Persistence / Projects | 未开始 |
| — | SVG Debug（`solver.visualize`） | ✅ 开发工具（非正式产品 Phase） |

**下一轮禁止**因旧表误判而重做 Phase 3 评价或**推倒四区工作台**；优先收口 **3.5**，Desktop **围绕现结构加深**，装包与 **CSP** 走 **Phase 5**。

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

## Phase 3.5 — Evaluation Consolidation（← 当前）

把「能打分」收成「可解释、单所有权、可编排」：

- [x] **DesignFinding**（severity / severity / recommended_action）
- [x] **Metric Ownership**（`ownership.py`：原始 metric 只进一个轴）
- [x] Inspector 按 优势 / 注意 / 问题 / 说明 分组
- [x] `LayoutCandidate.evaluation`；pipeline 写入；**API 禁止重评**
- [x] Backend 拆分：`routes` / `schemas` / `services`；`python -m backend`
- [ ] 评价层与 Desktop 文案持续对齐；避免再引入平行分数模型

仍收紧：API 仅编排、Evaluator 不改几何、Renderer 只渲染。

---

## Phase 4 — Desktop Workbench（🟡 MVP）

**结构已锁定：围绕加深，禁止推倒重做四区工作台。**

```text
┌ Requirements ┬──────── Floorplan ────────┬ Inspector ┐
│              │                           │           │
│ Site         │                           │ Score     │
│ Program      │        FLOOR PLAN         │ Findings  │
│ Constraints  │                           │ Metrics   │
│ Preferences  │                           │ Rooms     │
│              │                           │           │
└──────────────┴───────────────────────────┴───────────┘
│                   Candidate Strip                    │
└─────────────────────────────────────────────────────┘
```

- [x] FastAPI：`/api/health` · `/api/generate`
- [x] React 四区 + SVG；仓库根 `pnpm dev`（引擎 + Vite）
- [x] UI 文案「引擎就绪」；不教用户手敲 uvicorn
- [ ] 左栏加深：Constraints / Preferences 分区（仍在 Requirements 柱内）
- [ ] 右栏加深：Rooms 明细与七轴 / Findings 同列
- [ ] 真正「打开即用」→ 依赖 Phase 5

开发工具：`uv run python -m solver.visualize`（SVG debug，非正式 UI）。

---

## Phase 5 — Local Runtime / Sidecar / Packaging（未完成）

目标：用户不知道 Python / uvicorn / 端口存在；发布包可验收。

| 项 | 状态 |
|----|------|
| `uv run python -m backend` / `pnpm dev` 一键开发 | ✅ |
| Tauri `setup` spawn 引擎 + 退出 kill | ✅ 骨架 |
| `bundle.externalBin` + `scripts/build_backend_sidecar.*` | ✅ 骨架 |
| 本机 `tauri:build` 装包验收（需 Rust） | ❌ |
| 发布态零 Python 环境 | ❌ |
| **Tauri CSP**：开发期 `csp: null` 可接受；**正式打包前必须收紧**（禁止长期保持 null） | ❌ 明确任务 |

CSP 收紧时机：与 sidecar 真装包同一验收门禁，不在 Phase 4 提前严配（以免拖慢 Desktop 加深）。

---

## Phase 6 — Local LLM（未开始）

```text
Natural Language → (Ollama) → RequirementSpec → normalize → Solver
```

禁止 LLM 输出坐标 / SVG / DesignProgram。

---

## Phase 7+（未开始）

- **7** Interactive Editing（拖拽房间等）
- **8** Persistence / Projects（本地项目存取）

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
| **当前主线** | Phase 3.5 收口 → Phase 5 Sidecar |

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

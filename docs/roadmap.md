# PlanSeed 路线图

> 当前焦点：**Phase 1.5 — Solver Reliability**  
> 不要被「32 candidates + Top5 + tests passed」迷惑：切矩形 ≠ 设计住宅。

## 阶段总览

| Phase | 主题 | 状态 |
|-------|------|------|
| 0 | Architecture Foundation | ✅ |
| 1 | Deterministic Layout Core | ✅ 基本完成 |
| **1.5** | **Solver Reliability** | ✅ 收口 |
| **1.6** | **Spatial Semantics Hardening** | **← 进行中**（core 禁止缩小；north_angle；Functional≠WetStack；`WetStack` + `max_wet_stacks=1`） |
| **2.0** | **Topology-driven pack** | **MVP ✅**（`RoomGraph → TopologyPlan` 影响区内打包序） |
| **2.1** | **AccessGraph + connections** | 未开始（拓扑可达 / 必连 / 共享边；**先于画门**） |
| **2.2** | **Door placement** | 未开始（依赖 2.1 的共享边界） |
| 2 | Spatial Topology + Circulation（总览） | 2.0 ✅ → 2.1 AccessGraph → 2.2 Door |
| 3 | Architectural Evaluation | 未开始 |
| 4 | Minimal Visual Debugger（SVG debug） | ✅ 初版 |
| 5 | FastAPI | 延后 |
| 6 | LLM Requirement Parsing | 延后 |
| 7 | Tauri UX | 延后 |
| 8 | Interactive Editing | 延后 |
| 9 | Persistence / Projects | 延后 |
| 10 | Packaging | 延后 |

**FastAPI / Tauri / LLM 在 Phase 1.5 与拓扑闭环之前不做。**

Visual Debugger（Phase 4）安排在 FastAPI 之前：纯 JSON 已难以判断方案好坏。

---

## Phase 1.5 — Solver Reliability

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

### P1 Floor Assignment（✅ 已完成；语义边界见下）

```text
Rooms → FloorAssignmentSolver → floor.room_ids
```

Generator 不猜楼层。

**语义边界（Phase 1.6 / 2）：** 住宅规则以 `RoomSpec.tags` 为准；`name` 是 UI 文本。  
中文 name 子串回退冻结在 `solver/semantics/roles.py`，**禁止**再为「父母房 / 西厨 / 影音室」等加 `in name`。  
自然语言 → tags 由 normalize / Phase 6 LLM 负责；Solver 不承担 NLP。

---

### P2 StairCore（✅ 已完成；1.6 加固：禁止缩小）

```text
1.6×整进深条带  →  StairCore ~1.8×4.2，N/S/E/W/center
放不下 → 换 orientation / placement → 仍不行 → geometry.core_unfit（不缩放）
```

### P3 Architectural Zones（✅ 初版）

```text
building envelope
      ↓
StairCore
      ↓
Zones (day / night / service)
      ↓
Rooms（Guillotine = RoomLayout strategy）
```

`ZonePlanner`：功能区（DAY/NIGHT/SERVICE）与技术叠组（`WetStack`）分离；  
厨房→DAY+WS1，主卫→NIGHT+WS1，客卫→SERVICE+WS1。  
MVP：`SolverConfig.max_wet_stacks=1` → 整栋至多一个 `WetStack`（WS1）；未来可扩 WS2。

---

## 目标生成流水线（下一代）

```text
DesignProgram
      ↓
FloorAssignment
      ↓
RoomGraph
      ↓
TopologyPlan              ← Phase 2.0 MVP（邻接簇 / pack_order / avoid）
      ↓
ZonePlanner
      ↓
CorePlacement
      ↓
ZoneGeometry
      ↓
RoomLayout (Guillotine = strategy；区内序读 TopologyPlan)
      ↓
AccessGraph + required connections   ← Phase 2.1
      ↓
Shared boundary → Door placement     ← Phase 2.2
      ↓
ConstraintChecker
      ↓
Evaluator
```

Guillotine **保留**，但不再决定整栋住宅组织。RoomGraph 须影响生成，而非仅事后打分。

---

## Phase 2.0 — Topology-driven pack（✅ MVP）

```text
RoomGraph → TopologyPlan → Zone placement → Room placement
```

- `TopologyPlanner`（`solver/topology/plan.py`）从邻接/近邻/回避边产出簇与 `pack_order_hint`
- Guillotine **不再** `shuffle` 决定结构；拓扑序确定性，`rng` 仅扰动切分几何
- 本切片**不**重划 DAY/NIGHT；**不做** AccessGraph / 门洞

## Phase 2.1 — AccessGraph（下一优先；先于画门）

**禁止**：矩形摆好就直接 `place door`。

正确顺序：

```text
Room topology
      ↓
AccessGraph
      ↓
Required connections
      ↓
Shared boundary
      ↓
Door placement          ← 仅 Phase 2.2
```

示例（住宅可达树，先是图，不是洞口）：

```text
Entry
  ↓
Foyer
  ↓
Living
  ↓
Hall
  ├ Bedroom A
  ├ Bedroom B
  └ Bathroom
```

2.1 交付物：

- **`SpaceConnection`**：`a` / `b` / `type`（OPEN|DOOR|PASSAGE|STAIR|EXTERIOR_ENTRY）/ `required`
  - 邻接 ≠ 通行：Kitchen—Dining 可用 `AdjacencyConstraint`；Hall—Bedroom 用 `SpaceConnection(type=DOOR)`
- **`AccessGraph`**：由 SpaceConnection 构成（`DesignProgram.access_graph`）
- Required connections：从 constraints / 住宅默认规则派生
- Shared boundary 查询：两节点是否同层共边、共边几何段
- Validation：`unreachable room` 作为 hard（相对入口/楼梯）
- **仍不画门**；SVG 可先画「应连通」虚线边

语义标签硬化可并行：tags 为唯一规则入口（淘汰 Solver 侧中文 name 回退）。

```text
「父母房」  →  tags=[bedroom, elderly_accessible]   # LLM / normalize
FloorAssignment / ZonePlanner / AccessGraph 只读 tags，不读 name
```

## Phase 2.2 — Door placement

在 2.1 确认「谁必须通谁」且存在共享边之后：

- 在 shared boundary 上放置 Opening / Door
- 门宽、侧铰、净宽校验
- SVG 画门洞

无 AccessGraph 与共享边，禁止凭空在墙上戳门。

---

## Phase 4：SVG Debug（✅ 初版）

```bash
uv run python -m solver.visualize
# 或：uv run python -m solver.visualize --out debug --top 5
```

输出 `debug/candidate_0N_seedXX.svg`（房间名/面积、category 色、core、wet 虚线框、score/metrics、hard violations）。  
非正式 UI，供 generator 回归目视检查。后续可加 AccessGraph 边、violation 高亮、对齐轴；门洞在 2.2。

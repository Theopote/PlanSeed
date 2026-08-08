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
| **2.1** | **AccessGraph + connections** | **进行中**（✅ unreachable；✅ 默认软边派生；✅ 2A 共边→Door；✅ SVG 虚线） |
| **2.2** | **Door placement polish** | 未开始（铰链/净宽/SVG；**仍不回改房间几何**） |
| 2 | Spatial Topology + Circulation（总览） | 2.0 ✅ → 2.1 → 2A ✅ → 2.2；拓扑驱动几何延后 |
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

## 目标生成流水线（Phase 2 终态）

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
Graph-aware Room Ordering     ← 非 shuffle；簇整组进 slicing
      ↓
Guillotine
      ↓
ConnectionResolver            ← 必连 ↔ 共边
      ↓
DoorPlacement                 ← 只标开口，不回改房间几何（2A）
      ↓
AccessibilityValidator        ← access.unreachable_room 等
      ↓
Evaluator
```

这已接近小型建筑空间生成系统：关系驱动布局，几何事后验证，门不反向炸掉房间。

### Graph 反向驱动 Generator（渐进）

| 阶段 | 行为 |
|------|------|
| ~~纯 `rng.shuffle(rooms)`~~ | ❌ 已淘汰 |
| **2.0 ✅** | `TopologyPlan.pack_order_hint` + adjacency cluster 连续序 |
| **2.0.1 ✅** | `[Kitchen,Dining,Living]` 作为 **同一 slicing group** 进入切分（组间不拆簇；组内可再切） |
| **2.1 ✅ 软驱动** | 默认 AccessGraph + 高连通度打包加权；硬必连仍显式 `required=True` |
| **下一步** | topology drives geometry（为满足必连调整切分，仍尽量不全局重优化） |

示例簇：

```text
Kitchen — Dining — Living  →  cluster [K, D, L]  →  同组 Guillotine slice
```

---

## Phase 2.0 — Topology-driven pack（✅ MVP）

```text
RoomGraph → TopologyPlan → Zone placement → Room placement
```

- `TopologyPlanner`（`solver/topology/plan.py`）从邻接/近邻/回避边产出簇与 `pack_order_hint`
- Guillotine **不再**纯 `shuffle`；区内序读 TopologyPlan；`rng` 仅扰动切分几何
- 邻接簇作为 **slicing group**：组间二分不拆簇；仅当当前矩形内只剩该簇时才解锁组内再切
- 本切片**不**重划 DAY/NIGHT

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
ExteriorEntry          ← SiteSpec.entrance_edge / road_edges（≠ Stair）
  ↓
Foyer / Living / Hall
  ↓
…
StairCore              ← 仅竖向交通，不当作主入口
```

- **`ExteriorEntry`（✅）**：贴 buildable 外缘；AccessGraph 起点；楼梯命名仅为「楼梯」
- **Hard 第一原则（✅ MVP）**：`access.unreachable_room`
  - ExteriorEntry → SpaceConnection / 共边临时图 BFS
  - 任意 occupied room（`DesignProgram.rooms`）不在 reachable set → **candidate invalid**
- **`SpaceConnection`**：`a` / `b` / `type`（OPEN|DOOR|PASSAGE|STAIR|EXTERIOR_ENTRY）/ `required`
  - 邻接 ≠ 通行：Kitchen—Dining 可用 `AdjacencyConstraint`；Hall—Bedroom 用 `SpaceConnection(type=DOOR)`
- **`AccessGraph`**：由 SpaceConnection 构成（`DesignProgram.access_graph`）；校验时回退共边+入口贴边+楼梯叠置
- **默认派生（✅）**：`derive_residential_access_graph` — hub↔卧室/客卫 DOOR、厨餐 OPEN 等为 **soft**（`required=False`）；硬必连仍需用户显式边
- **高连通度打包**：AccessGraph 边权抬升 TopologyPlan hub
- **软评价**：`access_pref_satisfaction` → `circulation_score`
- Required connections：用户 `SpaceConnection(required=True)` / `AccessConstraint.requires_exterior`
- Shared boundary 查询：`shared_boundary_between`（doors）
- SVG：应连通虚线边（`access_graph=`）
- **仍不**为连通回改房间几何（topology drives geometry 延后）

语义标签硬化可并行：tags 为唯一规则入口（淘汰 Solver 侧中文 name 回退）。

```text
「父母房」  →  tags=[bedroom, elderly_accessible]   # LLM / normalize
FloorAssignment / ZonePlanner / AccessGraph 只读 tags，不读 name
```

## Phase 2A — 共边校验 + DoorOpening（✅；禁止回改几何）

**第一版绝对不做**：为放门重新优化所有房间。否则 Phase 2 爆炸。

```text
geometry（已有 RoomPlacement）
      ↓
required SpaceConnection
      ↓
shared_edge_length >= minimum ?
      ├─ yes → 标注 DoorOpening（不改房间矩形）
      └─ no  → access.missing_shared_boundary（invalid）
```

当前阶段是 **geometry → topology validation**。  
**topology drives geometry** 留给更晚阶段。

## Phase 2.2 — Door polish（仍不回改房间）

在 2A 共边开口之上：

- 门宽、侧铰、净宽校验
- SVG 画门洞

无共边仍禁止凭空戳门；**仍禁止**为门重跑 Guillotine。

---

## Phase 4：SVG Debug（✅ 初版）

```bash
uv run python -m solver.visualize
# 或：uv run python -m solver.visualize --out debug --top 5
```

输出 `debug/candidate_0N_seedXX.svg`（房间名/面积、category 色、core、wet 虚线框、score/metrics、hard violations）。  
非正式 UI，供 generator 回归目视检查。后续可加 AccessGraph 边、violation 高亮、对齐轴；门洞在 2.2。

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
| **2.1** | **AccessGraph + connections** | **✅ 主线**（unreachable；软边；2A Door；SVG；局部修补；**跨区重切**） |
| **2.2** | **Door placement polish** | **✅**（铰链/净宽 soft / SVG 门扇；**仍不回改房间几何**） |
| **2.3** | **Realized Circulation** | **✅**（共墙≠通行；RealizedAccessGraph；soft 开口；RepairRecord/Budget；spanning OPEN） |
| 2 | Spatial Topology + Circulation（总览） | 2.0 ✅ → 2.1 → 2A ✅ → 2.2；拓扑驱动几何延后 |
| 3 | Architectural Evaluation | ✅ MVP |
| **3.5** | **System Consolidation / DesignFinding** | **✅ MVP** |
| 4 | Minimal Visual Debugger（SVG debug） | ✅ 初版 |
| 5 | FastAPI | **✅ MVP**（`/api/health` · `/api/generate`） |
| 6 | LLM Requirement Parsing | 延后 |
| 7 | Tauri UX | **✅ MVP 壳**（四区 + SVG；`pnpm tauri:dev` 需 Rust） |
| 8 | Interactive Editing | 延后 |
| 9 | Persistence / Projects | 延后 |
| 10 | Packaging | 延后 |

**Solver / 拓扑 / Phase 3 评价已就绪。** Desktop MVP：FastAPI + Vite/Tauri 四区壳；LLM / 编辑 / 打包仍延后。

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
| **2.1.1 ✅** | ConnectionResolver：必连小缝 / 短共边 **局部修补**（不全局重排） |
| **2.1.2 ✅** | 同层小 AABB **跨区局部重切**：必连对先共边占位，其余在剩余矩形打包 |
| **2.1.3 ✅** | **绕核 / 多 free-rect**：楼梯核固定挖洞；必要时扩绕行带再打包（仍不动核） |
| **下一步** | Sidecar 打包；交互编辑；LLM（均延后） |

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
- **局部几何（✅ 2.1.1）**：`resolve_required_connections` 闭合 ≤1.5m 缝隙 / 加长短共边
- **跨区重切（✅ 2.1.2）**：局部失败后在小 AABB 内重切（≤6 房、≤55% 楼层、距≤8m）
- **绕核重切（✅ 2.1.3）**：AABB 含楼梯核时**挖洞**为多块 free rect；互不连通则扩绕行带；核矩形不变；踩非成员外人仍放弃
- **仍不**整层为连通重跑 Guillotine

语义标签硬化可并行：tags 为唯一规则入口（淘汰 Solver 侧中文 name 回退）。

```text
「父母房」  →  tags=[bedroom, elderly_accessible]   # LLM / normalize
FloorAssignment / ZonePlanner / AccessGraph 只读 tags，不读 name
```

## Phase 2.3 — Realized Circulation（✅ 主线）

核心原则：

```text
Adjacency / 共墙  ≠  Access Intent  ≠  Realized Access
```

- **删除** `shared wall → PASSAGE` 自动边
- Reachability 只走 `RealizedAccessGraph`（ExteriorEntry / DoorOpening / Stair / stair_access / spanning OPEN）
- soft Intent 可实现时也会生成开口；required 失败 → hard；soft 失败 → `access.preferred_blocked`
- `RepairRecord` + `SolverConfig` repair budget；`layout_stability` metric
- 同层共墙连通分量 spanning-tree → **显式 OPEN**（仍不是「共墙即通行」）

---

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

当前阶段：**geometry → ConnectionResolver（缝隙修补 → 局部重切 → 绕核多 free-rect）→ DoorOpening**。  
更激进的整层重切仍禁止。

## Phase 2.2 — Door polish（✅；仍不回改房间）

在 2A 共边开口之上：

- **门宽 / 净宽**：`DoorOpening.clear_width`；`< 0.8m` → soft `door.clear_width`
- **开启方向**：优先开入 private（避免堵走廊）→ `swing_room_id`
- **侧铰**：`hinge_side` / `hinge_x|y`（面门约定 left/right）
- **SVG**：洞口粗线 + 铰链点 + 90° 开启弧

无共边仍禁止凭空戳门；**仍禁止**为门重跑 Guillotine。

---

## Phase 3 — Architectural Evaluation（✅ MVP）

在 Realized Circulation 之上上做**可解释**建筑评价（Evaluator 只评分，不改几何）：

| 用户轴 | 模块 | 要点 |
|--------|------|------|
| Program | `program_fit.py` + adjacency | 清单覆盖 / 面积份额 / 邻接 |
| Spatial | geometry + compactness | 比例 / 紧凑度（面积归 Program） |
| Circulation | `circulation.py` + `access.py` | realized 可达 / 深度 / 穿堂 |
| Privacy | `privacy.py` | entry→private 过渡；穿卧惩罚 |
| Environment | `orientation.py` | 朝向 / 外墙；采光后续 |
| Technical | `vertical.py` + entry/site | 楼梯 / 湿区 / 入口 / 临路 |
| Robustness | repair metrics | ConnectionResolver / reslice 稳定性 |

`DesignScore` 为七轴 + `findings[]`；`explanations` / `warnings` 由 findings 派生。  
**不做**：daylight；LLM；房间拖拽编辑。

---

## Phase 3.5 — System Consolidation / DesignFinding（✅ MVP）

评价从「报分数」升级为可解释设计发现：

```text
DesignFinding
  id / category / severity(INFO|POSITIVE|WARNING|PROBLEM)
  title / message / room_ids
  metric / measured_value / recommended_action
```

- `CompositeEvaluator` 聚合 circulation / privacy / program_fit / stability 等 findings
- `explanations` / `warnings` 由 findings 派生（兼容旧字段）
- Desktop Inspector 按 **优势 / 注意 / 问题 / 说明** 分组展示
- **Metric Ownership**：原始 metric 只进一个轴（见 `ownership.py`）
- **七轴用户层**：Program / Spatial / Circulation / Privacy / Environment / Technical / Robustness

仍收紧中：API 仅编排、Evaluator 不改几何、Renderer 只渲染。

---

## Phase 4：SVG Debug（✅ 初版）

```bash
uv run python -m solver.visualize
# 或：uv run python -m solver.visualize --out debug --top 5
```

输出 `debug/candidate_0N_seedXX.svg`（房间名/面积、category 色、core、wet、entry、access 虚线、**门洞/开启弧**、score/metrics、hard violations）。  
非正式 UI，供 generator 回归目视检查。

---

## Phase 5 / 7 — Desktop UI MVP（✅）

```text
Left: Requirements / Program
Center: Floorplan (SVG from solver)
Right: Inspector (DesignScore breakdown)
Bottom: Candidate Strip (A 91, B 89…)
```

- API：`uv run uvicorn backend.main:app --port 8787`
- UI：`cd desktop && pnpm dev`（或 `pnpm tauri:dev`）
- `POST /api/generate`：RequirementSpec 或 `use_benchmark` → pipeline → SVG + 分项分

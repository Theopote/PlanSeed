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
| 2 | Spatial Topology + Circulation（门 / AccessGraph） | 未开始 |
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
ZonePlanner
      ↓
CorePlacement
      ↓
ZoneGeometry
      ↓
RoomLayout (Guillotine = strategy)
      ↓
Door / Connectivity          ← Phase 2
      ↓
ConstraintChecker
      ↓
Evaluator
```

Guillotine **保留**，但不再决定整栋住宅组织。

---

## Phase 2 预告：门与可达性 + 语义标签硬化

矩形堆砌不是住宅。Phase 2 引入：

- Door / Opening / Connection / AccessGraph
- `unreachable room` 作为 hard validation
- **tags / semantic role 成为唯一规则入口**（淘汰 Solver 侧中文 name 回退）

可达性比「客厅是否 24㎡」更重要。

示例：

```text
「父母房」  →  tags=[bedroom, elderly_accessible]   # LLM / normalize
FloorAssignment / ZonePlanner 只读 tags，不读 name
```

---

## Phase 4：SVG Debug（✅ 初版）

```bash
uv run python -m solver.visualize
# 或：uv run python -m solver.visualize --out debug --top 5
```

输出 `debug/candidate_0N_seedXX.svg`（房间名/面积、category 色、core、wet 虚线框、score/metrics、hard violations）。  
非正式 UI，供 generator 回归目视检查。后续可加门洞、violation 高亮、对齐轴。

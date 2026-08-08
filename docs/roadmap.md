# PlanSeed 路线图

> 当前焦点：**Phase 1.5 — Solver Reliability**  
> 不要被「32 candidates + Top5 + tests passed」迷惑：切矩形 ≠ 设计住宅。

## 阶段总览

| Phase | 主题 | 状态 |
|-------|------|------|
| 0 | Architecture Foundation | ✅ |
| 1 | Deterministic Layout Core | ✅ 基本完成 |
| **1.5** | **Solver Reliability** | **← 现在** |
| 2 | Spatial Topology + Circulation（门 / AccessGraph） | 未开始 |
| 3 | Architectural Evaluation | 未开始 |
| 4 | Minimal Visual Debugger（SVG debug） | 未开始 |
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
- [x] Missing room detection（`ensure_floor_assignment` / `assert_all_rooms_placed`）
- [x] Duplicate room assignment detection
- [x] Floor assignment consistency
- [x] RequirementSpec assumption / unknown tracking
- [x] Orientation evaluator 闭环
- [x] Quality regression 门槛

### P1 Floor Assignment（✅ 已完成）

```text
Rooms → FloorAssignmentSolver → floor.room_ids
```

Generator 不猜楼层。

### P2 StairCore（✅ 已完成）

```text
1.6×整进深条带  →  StairCore ~1.8×4.2，N/S/E/W/center
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

`ZonePlanner`：`packages/schema/zoning.py` + `solver/topology/zoning.py`  
后续可加强 zone 邻接、入口关系、与 RoomGraph 联动。

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

## Phase 2 预告：门与可达性

矩形堆砌不是住宅。Phase 2 引入：

- Door / Opening / Connection / AccessGraph
- `unreachable room` 作为 hard validation

可达性比「客厅是否 24㎡」更重要。

---

## Phase 4 预告：SVG Debug

```bash
uv run python -m solver.visualize
```

输出 `debug/candidate_0N.svg`（房间、面积、category、core、violation、score）。  
非正式 UI，供 generator 回归目视检查。

# Schema v2 设计

## 设计原则

1. **输入与输出分离**：`RoomSpec` 描述需求，`RoomPlacement` 描述 solver 输出。
2. **场地三层分离**：`site_boundary` / `buildable_envelope` / `building_footprint` 语义不可混用。
3. **约束统一模型**：所有约束带 `hard` / `weight`，hard 违反 → invalid candidate。
4. **可扩展**：MVP 仅矩形地块与正交房间，但 schema 不阻止未来多边形与曲线墙。

## 根对象：ProjectSpec

```python
ProjectSpec
├── id, name, version
├── site: SiteSpec
├── household: HouseholdSpec
├── floors: list[FloorSpec]      # 1–3 层
├── rooms: list[RoomSpec]
├── constraints: list[Constraint]
└── preferences: PreferencesSpec
```

## SiteSpec

| 字段 | 说明 |
|------|------|
| `width`, `depth` | 矩形用地尺寸（米） |
| `north_angle` | 正北相对 model north 外向的顺时针角；见 `SiteCoordinateSystem` |
| `entrance_edge` | 主入口边（驱动 **ExteriorEntry**，≠ 楼梯） |
| `road_edges` | 临路边（入口宜对齐；`ExteriorEntry.on_road_edge`） |
| `setbacks` | 四向退线 |
| `site_boundary` | 用地外轮廓（默认可由 width×depth 推导） |
| `buildable_envelope` | 退线后可建范围（默认由 setbacks 推导） |
| `building_footprint` | 建筑占地（solver 输出回填） |
| `stair_width`, `grid_module`, `structural_module` | 楼梯宽与模数 |

`SiteSpec` 在 validate 时自动推导缺失的 `site_boundary` 与 `buildable_envelope`。

## RoomSpec

| 字段 | 说明 |
|------|------|
| `id`, `name`, `category` | 标识与功能分类 |
| `target_area`, `min_area`, `max_area` | 面积目标与区间 |
| `min_width` | 最小净宽 |
| `floor_id`, `floor_preference` | 楼层约束与偏好 |
| `daylight_required` | 是否需要采光 |
| `preferred_orientation` | 朝向偏好 |
| `privacy_level` | 私密等级 |
| `exterior_access` | 是否需要对外出口 |
| `tags` | **语义角色**（`kitchen`, `bedroom`, `master`, `elderly_accessible`…）；Solver 主判定依据。`name` 仅为 UI 文本 |

`category` 枚举：`public | private | wet | service | circulation | other`

## 约束模型 Constraint

Discriminated union，按 `kind` 区分：

| 类型 | 用途 |
|------|------|
| `AdjacencyConstraint` | 几何邻接（共享墙）；**不等于**可通行 |
| `SeparationConstraint` | 两房间分离 / 最小距离 |
| `OrientationConstraint` | 朝向偏好（默认 soft） |
| `FloorConstraint` | 强制楼层 |
| `AlignmentConstraint` | 跨层对齐（湿区、楼梯） |
| `AreaConstraint` | 面积 hard/soft |
| `WidthConstraint` | 最小宽度 hard |
| `AccessConstraint` | 单房间对外 / 楼梯可达（遗留；2.1 以 AccessGraph 为主） |

### SpaceConnection / AccessGraph（Phase 2.1）

```python
SpaceConnection(a, b, type=OPEN|DOOR|PASSAGE|STAIR|EXTERIOR_ENTRY, required)
AccessGraph(node_ids, connections[])
```

- **邻接**（AdjacencyConstraint）：Kitchen—Dining 可贴邻而无门
- **通行**（SpaceConnection）：Hall—Bedroom 必须可走通
- AccessGraph 由 SpaceConnection 构成；Door placement（2.2）只消费已确认共享边的 DOOR/PASSAGE 等

每个约束包含：`id`, `kind`, `hard`, `weight`, `description`

## 输出模型

### RoomPlacement

```python
room_id, floor_id, x, y, width, depth
```

### LayoutCandidate

```python
id, seed, floors[], validation, score, metrics
```

### CandidateValidation

```python
valid, hard_violations[], soft_violations[], warnings[]
```

### Violation

```python
constraint_id, room_ids[], message, measured_value, required_value, hard
```

## Solver 内部：DesignProgram

`normalize(ProjectSpec)` 产出：

```python
DesignProgram
├── project_id, site, buildable
├── floors, rooms, constraints
├── room_graph: RoomGraph
└── solver_config: SolverConfig
```

`SolverConfig`：`candidate_count=32`, `return_top_k=5`, `base_seed=42`, `snap_module=0.3`

## RoomGraph / TopologyPlan / AccessGraph

```python
RoomGraph
├── room_ids[]
└── edges[]: RoomEdge(source, target, kind, weight)

TopologyPlan                    # 生成前打包序（2.0）
├── clusters[]: AdjacencyCluster(floor_id, room_ids)
├── prefer_adjacent[]: RoomPair
├── avoid_pairs[]: RoomPair
└── pack_order_hint: {floor_id: [room_id…]}

AccessGraph                     # 可达（2.1）；边 = SpaceConnection
├── node_ids[]                  # 房间 + exterior-entry / stair …
└── connections[]: SpaceConnection(a, b, type, required)

ExteriorEntry                   # 对外主入口（≠ StairCore）
├── id = "exterior-entry"
├── edge ← SiteSpec.entrance_edge
├── on_road_edge ← entrance_edge ∈ road_edges
└── connected_room_ids          # 厅/门厅优先，楼梯垫底
```

Edge kind（RoomGraph）：`adjacent | connected | near | far | avoid`  
SpaceConnection type：`open | door | passage | stair | exterior_entry`  
交通起点：`ExteriorEntry → Foyer / Living / Hall → …`（楼梯只做竖向，不当入口）

## 从 v1 迁移映射

| v1 (旧手册) | v2 |
|-------------|-----|
| `Room.area` | `RoomSpec.target_area` |
| `Room.type` | `RoomSpec.category` |
| `SiteConfig.width/depth` | `SiteSpec.width/depth` |
| `SiteConfig.stair_width` | `SiteSpec.stair_width` |
| `SiteConfig.module` | `SiteSpec.structural_module` |
| 输出 `rect` on room | `RoomPlacement` |
| 无 constraints | `constraints[]` + implicit from RoomSpec |

## JSON Schema / LLM

LLM structured output 使用：

```python
ProjectSpec.model_json_schema()
```

不维护第二份手写 JSON Schema。

## 实现位置

```text
packages/schema/
├── project.py      # ProjectSpec, HouseholdSpec, PreferencesSpec
├── site.py         # SiteSpec, SetbackSpec, Rect2D
├── room.py         # RoomSpec, FloorSpec
├── constraints.py  # Constraint union
├── layout.py       # RoomPlacement, LayoutCandidate
├── scoring.py      # DesignScore, DesignMetrics
├── program.py      # DesignProgram, SolverConfig
└── topology.py     # RoomGraph, RoomEdge
```

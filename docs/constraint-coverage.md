# Constraint Coverage Audit（Phase 1.6）

> 标记定义了但未闭环的约束，避免「schema 存在 = 已生效」的幻觉。

| Constraint | Schema | Normalize | Generate | Validate | Evaluate | Tests | 备注 |
|---|---|---|---|---|---|---|---|
| AdjacencyConstraint | ✓ | 部分（偏好） | — | ✓ hard/soft | ✓ soft sat | ✓ | hard 邻接已闭环 |
| SeparationConstraint | ✓ | — | — | ✓ hard/soft | — | ✓ | checker 最小距离 |
| OrientationConstraint | ✓ | ✓ 偏好 | — | ✓ hard | ✓ soft score | ✓ | **north_angle 感知** |
| FloorConstraint | ✓ | ✓ FloorAssignment | — | ✓ hard/soft | — | ✓ | FloorAssignment + checker 双验 |
| AlignmentConstraint | ✓ | ✓ wet_stack | ✓ WetStack anchor | ✓ | ✓ vertical | ✓ | stair/wet |
| AreaConstraint | ✓ | — | — | ✓ hard/soft | area_accuracy | ✓ | soft 不再丢弃 |
| WidthConstraint | ✓ | — | — | ✓ hard/soft | — | ✓ | soft 不再丢弃 |
| AccessConstraint | ✓ | ✓ → SpaceConnection | — | ✓ hard/soft | — | ✓ | stair_reach / requires_exterior |
| SpaceConnection / AccessGraph | ✓ | ✓ 默认软边 | ✓ 连通度序 | ✓ unreachable / 共边 | ✓ circulation | ✓ | 硬必连需 required=True |

## 系统级 / 语义（Phase 1.6）

| 能力 | Schema | Generate | Validate | Evaluate | Tests | 备注 |
|---|---|---|---|---|---|---|
| StairCore / core unfit | ✓ | ✓ 禁止缩小 | ✓ geometry.core_* | — | ✓ | 放不下 → invalid |
| WetStack ≠ Functional Zone | ✓ | ✓ WS1 锚 | ✓ 对齐 | ✓ wet_stack_alignment | ✓ | wet_zone_* legacy |
| SiteCoordinateSystem / north_angle | ✓ | — | ✓ orient hard | ✓ orient score | ✓ | `site_coords.py` |
| ExteriorEntrySpec / Placement | ✓ | ✓ | — | soft entry_on_road | ✓ | ≠ Stair；SVG 标注 |
| semantic_role / tags | ✓ | FloorAssign / Zone | — | — | ✓ | role→tags→name |
| Road soft preference | site.road_edges | entry 标记 | — | entry/garage_on_road | ✓ | **非 hard** |
| RoomGraph helpers | ✓ | — | — | — | ✓ | degree/components/… |

## 系统级几何校验

| ID | Validate | Tests |
|---|---|---|
| geometry.overlap | ✓ | ✓ |
| geometry.boundary | ✓ | ✓ |
| geometry.missing_room | ✓ | ✓ |
| geometry.duplicate_room | ✓ | ✓ |
| geometry.wrong_floor | ✓ | ✓ |
| geometry.unknown_room | ✓ | ✓ |
| geometry.core_unfit | ✓ | ✓ |
| geometry.core_missing | ✓ | ✓ |
| geometry.core_size | ✓ | ✓ |
| access.unreachable_room | ✓ | ✓ |
| access.missing_shared_boundary | ✓ | ✓ |
| access.preferred_blocked | ✓ soft | ✓ |
| door.clear_width / physical_min | ✓ soft | ✓ |
| repair.budget_exceeded | ✓ | ✓ |

## 结论

- **Adjacency ≠ Access Intent ≠ Realized Access**（Phase 2.3）
- Separation / Floor / Access：checker 已接线（hard invalidates；soft → soft_violations）
- Door：Intent 可实现则落开口（含 soft）；共墙 alone 不可通行；spanning-tree OPEN 为显式开口
- FloorConstraint：FloorAssignmentSolver 消费 + checker 复核 placement.floor_id
- Generator 不「理解」约束语义；靠 zone/core + checker/evaluator 闭环

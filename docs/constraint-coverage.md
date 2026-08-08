# Constraint Coverage Audit（Phase 1.5）

> 标记定义了但未闭环的约束，避免「schema 存在 = 已生效」的幻觉。

| Constraint | Schema | Normalize | Generate | Validate | Evaluate | Tests | 备注 |
|---|---|---|---|---|---|---|---|
| AdjacencyConstraint | ✓ | 部分（偏好） | — | ✓ hard/soft | ✓ soft sat | ✓ | hard 邻接已闭环 |
| SeparationConstraint | ✓ | — | — | — | — | — | **未接线** |
| OrientationConstraint | ✓ | ✓ 偏好 | — | ✓ hard | ✓ soft score | ✓ | 轴对齐外墙；非日照分析 |
| FloorConstraint | ✓ | ✓ FloorAssignment | — | 归属阶段 | — | ✓ | 不在 checker 再验 |
| AlignmentConstraint | ✓ | ✓ wet_stack | ✓ wet AABB | ✓ | ✓ vertical | ✓ | stair/wet |
| AreaConstraint | ✓ | — | — | ✓ hard/soft | area_accuracy | ✓ | soft 不再丢弃 |
| WidthConstraint | ✓ | — | — | ✓ hard/soft | — | ✓ | soft 不再丢弃 |
| AccessConstraint | ✓ | — | — | — | — | — | **Phase 2** |

## 系统级几何校验（非 Constraint 联合体成员）

| ID | Validate | Tests |
|---|---|---|
| geometry.overlap | ✓ | ✓ |
| geometry.boundary | ✓ | ✓ |
| geometry.missing_room | ✓ | ✓ |
| geometry.duplicate_room | ✓ | ✓ |
| geometry.wrong_floor | ✓ | ✓ |
| geometry.unknown_room | ✓ | ✓ |
| geometry.core_unfit | ✓ | ✓ | 规定尺寸放不下 → invalid，禁止缩小 |
| geometry.core_missing | ✓ | ✓ | |
| geometry.core_size | ✓ | ✓ | 尺寸必须等于 StairCoreSpec |

## 结论

- Separation / Access：**定义了但完全不起作用**（刻意留给 Phase 2 / 后续）
- FloorConstraint：由 FloorAssignmentSolver 消费，不重复进 layout checker
- Generator 不「理解」约束语义；靠 zone/core + checker/evaluator 闭环

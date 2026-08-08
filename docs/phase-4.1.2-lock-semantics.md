# Phase 4.1.2 — Lock Semantics Hardening

> **当前焦点（Phase 4 子阶段）。**  
> 目标：Lock 从「Generator 尽量尊重的提示」升级为贯穿几何流水线的**不可变设计契约**。  
> **禁止本阶段：** 自由拖拽深化、拖墙、resize、LLM、Persistence、CAD/BIM。  
> 总览：[roadmap.md](roadmap.md) · 契约：[api-contract.md](api-contract.md)

```text
4.0 Select/Edit ✅
4.1 Room/Stair Lock ✅ MVP
4.1.1 Zone Lock ✅ MVP
4.1.2 Lock Semantics Hardening ← 当前
4.2 Variant/Compare ✅
4.3 Constraint-aware Direct Manipulation（其后）
```

---

## 统一原则（4.3 前置，本阶段先写清）

未来所有改 placement 的路径必须服从 **Geometry Mutation Authority**：

```text
MutationRequest
  → LockGuard
  → GeometryValidator
  → Apply Mutation
  → Revalidate（含 lock invariant）
```

在此层落地前：**暂停**拖房间 / 拖墙 / 自由 resize 的产品深化（已有平移 MVP 可保留，不扩边角改尺寸）。

否则 drag · lock · snap · repair · reslice · regenerate 五套逻辑会互相打架。

---

## 优先级与落地状态（以代码为准）

| 级 | 项 | 状态 |
|----|----|------|
| **P0** | floor-local room/zone lock free space | ✅ `free_rects_by_floor` |
| **P0** | StairCore 才跨层占位 | ✅ |
| **P0** | post-processing 不得移动 Room/Stair lock（`protected_room_ids`） | ✅ |
| **P0** | final lock invariant（`lock.room_moved` / `stair_moved` / `zone_breached`） | ✅ |
| **P0** | `test_room_lock_is_floor_local` | ✅ |
| **P1** | `validate_layout_locks` + HTTP 422 | ✅ |
| **P1** | `ArchitecturalZone`；禁止非法 zone 静默忽略 | ✅ |
| **P1** | zone `room_ids` 校验；冲突/重叠 → invalid request | ✅ |
| **P1** | Room > Zone > Free 文档与 UI 文案 | ✅ |
| **P1** | `ZonePlacement.id` + `kind`；Lock = FunctionalZoneGroup | ✅ |
| **P1** | Resolver 禁止把 zone member **修到 envelope 外**（过程约束，不止最终 checker） | 🟡 最终 invariant 已有；过程护栏待补 |
| **P2** | Variant 发请求前 **locks 不可变快照** | 🟡 |
| **P2** | metrics：`lock_invariant_ok`（debug；不进七轴） | 🟡 |
| **P2** | UI polish / 更多回归（重叠锁、确定性、precedence 专测） | 🟡 |

详案条目（1–24）见下；已 ✅ 者不重复开工。

---

## 已完成要点（摘要）

1. **Floor-local holes** — 共享 free 只扣 StairCore；每层再扣本层 room/zone lock。  
2. **`ZonePlanner.plan_building(..., free_rects_by_floor=)`** — WetStack 仍用共享 free。  
3. **Immutable contract** — `resolve_required_connections` / reslice 尊重 `protected_room_ids`；失败 ≠ 解锁。  
4. **`check_lock_invariants`** — pipeline 合并进 validation。  
5. **`validate_layout_locks` / `LockValidationError` → 422**。  
6. **Zone identity** — `F1-day-0` 等；锁组语义 = FunctionalZoneGroup。

---

## 本阶段剩余（收口后停止）

1. Zone envelope **过程护栏**（repair 不得把 member 推出 envelope）  
2. Variant：`JSON`/`structuredClone` locks 快照再请求  
3. `lock_invariant_ok` metric  
4. 补测：zone member outside repair、overlapping locks、Room>Zone precedence、same seed+locks deterministic  
5. 文档：明确 **暂停拖拽深化**，下一产品步是 4.3

**不做：** free drag 深化、wall drag、resize handles、constraint solver 重写。

---

## Definition of Done（4.1.2）

1. Room Lock 只影响所属楼层；Stair Lock 仍跨层  
2. Resolver / Reslice 不能移动 locked room / stair  
3. locked zone envelope 不被后处理破坏（最终 + 过程）  
4. final checker 能发现 lock invariant violation  
5. invalid lock 生成前失败（422）  
6. 非法 zone 不再 silent ignore  
7. Room > Zone > Free 明确  
8. multi-floor lock 回归存在  
9. same seed + same locks 仍 deterministic  

完成后停止。下一阶段：

**Phase 4.3 — Constraint-aware Direct Manipulation**  
（有限编辑 + Geometry Mutation Authority；非自由 CAD）

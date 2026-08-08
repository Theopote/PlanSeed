# Phase 4.3 — Constraint-aware Direct Manipulation

> **当前产品步（4.1.2 Lock Semantics ✅ 之后）。**  
> 目标：受控直接编辑（Move / Resize），经统一 **Geometry Mutation Authority** 提交；  
> **不是**「带拖拽的 SVG demo」，更不是自由 CAD。  
> 总览：[roadmap.md](roadmap.md) · Lock 契约：[phase-4.1.2-lock-semantics.md](phase-4.1.2-lock-semantics.md)

```text
4.1.2 Lock Semantics Hardening ✅
4.3 Constraint-aware Direct Manipulation ✅（P0–P2）
4.3.1 Limited Shared-Wall Edit ✅
  ├─ ADJUST_WALL Authority
  ├─ 恰好两房共边 ≥0.9m；拒 T 接 / 楼梯
  └─ Commit 双侧 placements + upsert 双侧 Room Lock
```

---

## 前提（已满足，勿回退）

4.1.2 已把 Lock 升级为全流水线不可变约束：

| 风险 | 状态 |
|------|------|
| F1 Room Lock 扣掉 F2 free space | ✅ 已修 |
| ConnectionResolver 事后移动 locked geometry | ✅ protected + invariant |
| 非法 lock 静默忽略 | ✅ validate → 422 |

**因此可以进入 4.3。** 若再发现 lock 语义回归，优先修锁，不扩拖拽。

---

## 产品原则

### 禁止

```text
鼠标坐标 → 直接改 PlacementRect
```

### 必须

```text
用户拖动
  → ProposedMutation
  → Constraint Preview
  → 合法？
      ├─ yes → Commit
      └─ no  → 显示原因 / Snap Back
```

已有「松手写 Room Lock」的平移 MVP：**迁入** Mutation Authority，禁止继续在 `FloorplanView` 里旁路写 placements。

---

## GeometryMutation

统一变更类型（会话级，不进 RequirementSpec）：

| kind | 含义 |
|------|------|
| `MOVE` | 平移房间（楼梯核可后置） |
| `RESIZE` | 改 width/depth（边/角；本阶段有限） |
| `LOCK` | 写入 LayoutLocks（room / stair / zone group） |
| `UNLOCK` | 解除对应锁 |

建议模型（additive）：

```text
GeometryMutation:
  kind: MOVE | RESIZE | LOCK | UNLOCK
  room_id: str | null
  floor_id: str
  before: PlacementRect | null
  proposed: PlacementRect | null
  lock_payload: LayoutLocks fragment | null
  source: "pointer" | "inspector" | "system"
```

---

## Geometry Mutation Authority（唯一入口）

所有改 placement / locks 的操作必须走：

```text
ProposedMutation
  → LockGuard              # 不可动 locked room/stair；zone envelope 内约束
  → GeometryConstraintChecker  # buildable、重叠、snap、最小净宽…
  → AccessImpactChecker    # soft/hard：是否打断 required 共边（MVP 可先警告）
  → Commit                 # 写 session candidate placements ± upsert locks
  → Revalidate             # lock invariant + 可选轻量 validation
```

| 层 | 职责 |
|----|------|
| **LockGuard** | Zone member（无独立 Room Lock）不得出 envelope；不得侵入其它 Room/Stair lock；**本房 Room Lock 可经 MOVE Commit 更新** |
| **GeometryConstraintChecker** | 场地内、不重叠（或仅允许与 self）、snap_module、min width |
| **AccessImpactChecker** | P1：破坏 required 共边 → reject 或 warning+仍可 commit（产品选定一种） |
| **Commit** | 单一写入口；UI 只发 ProposedMutation |
| **Revalidate** | `check_lock_invariants`；失败则回滚 Commit |

前端指针层只产生 **proposed** 预览；**不得**在 pointermove 里当作已提交几何。

---

## 分期交付

### P0 — Authority + Move Room ✅

1. ✅ `packages/schema/mutation.py` + `solver/mutation/preview_mutation`  
   （~~桌面 `previewMove` 镜像规则~~ → **Phase 5.1 已收回** `POST /api/mutations/preview`）  
2. ✅ 拖拽松手 → `MOVE` → Guard → Commit（upsert Room/Stair Lock）或 Snap Back  
3. ✅ 非法：Snap Back + `mutationHint` 人话原因  
4. ✅ 测：`solver/tests/test_mutation.py`（buildable / overlap / zone envelope / snap）

### P1 — Resize Room ✅

1. ✅ 选中房间后边/角手柄 → `RESIZE` ProposedMutation  
2. ✅ 同 Authority：四边 snap、`≥0.9m` 硬拒；`min_width` / `resolved_min_area` soft 提示  
3. ✅ **不做**拖墙（墙是两房共享边界）

### P2 — Preview 体验 ✅

1. ✅ 拖动中虚线 proposed rect（snap 目标；冲突红 / soft 琥珀 / 合法绿）  
2. ✅ 冲突高亮（重叠 / 楼梯锁房间）  
3. ✅ AccessImpact 警告条（推断：丢失 ≥0.9m 共边邻居；soft，不挡 Commit）

### 4.3.1 — 有限共墙 ✅

1. ✅ `MutationKind.ADJUST_WALL` + `wall_axis` / `wall_coord` / `partner_room_id`  
2. ✅ `list_shared_walls`：恰好两房、≥0.9m、拒 T 接与楼梯  
3. ✅ Authority 双侧几何校验；非法 Snap Back；AccessImpact soft  
4. ✅ UI 共墙柄拖动；Commit 写两侧 placements 并 upsert 两侧 Room Lock  
5. ✅ 测：合法挪墙 / min_edge / 第三房重叠 / T 接不可枚举

---

## 与 Regenerate / Variant 的关系

| 操作 | 行为 |
|------|------|
| Commit MOVE/RESIZE/ADJUST_WALL | 通常 **自动 upsert Room Lock**（共墙 upsert 两侧） |
| Regenerate unlocked | 尊重 locks；未锁空间重排 |
| Create Variant | 同 program + **locks 快照**（4.1.2 已有 clone） |

禁止：Commit 后静默改其它 locked 几何。

---

## 明确不做（相对自由 CAD）

- T 接 / 三房以上联动推挤  
- 斜墙、整层 constraint solver 重写  
- 无约束自由 resize  
- LLM、Persistence、CAD/BIM  
- 绕过 Authority 的第二条写路径

---

## Definition of Done

1. ✅ 不存在「pointer → 直接写 PlacementRect」旁路（拖拽经 Authority）  
2. ✅ MOVE / RESIZE / ADJUST_WALL 经 LockGuard → GeometryChecker → Commit  
3. ✅ 非法 mutation：Snap Back + 可见原因；soft 提示不挡 Commit  
4. ✅ 不得侵入其它 locked room/stair；zone member（无 Room Lock）不出 envelope；本房锁可经编辑更新  
5. same seed + same locks 仍 deterministic；lock invariant 仍绿  
6. 文档与 UI 文案写清：受控编辑 ≠ 自由 CAD  

**4.3 / 4.3.1 已满足。** 下一产品步为 **Phase 5 血缘持久化**（见 [phase-5-persistence.md](phase-5-persistence.md)）。

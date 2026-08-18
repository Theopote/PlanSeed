# Proposal — Private Room Corridor Access Repair

> **状态：Implemented（2026-08-18）。** 对应 [ADR-011](../adr/011-corridor-access-repair.md)。

---

## 1. 问题背景与量化

默认 `benchmark_program()`、`candidate_count=64`：

| 阶段 | Top-5 `private_through_count > 0` |
|------|-----------------------------------|
| 修补前 | 5/5 (100%) |
| 修补后 | **0/5** |

典型路径（修补前 seed=45）：主入口 → … → 次卧1 → 主卫 → 主卧。

根因：`assign_residual_gaps_as_circulation` 只标记切分残余，不主动规划循环空间。

---

## 2. 修补算法（已实现）

实现位置：`solver/geometry/coverage.py`

### 2.1 触发条件

- `category == "private"`
- 无任何边与 `circulation` / `stair-*` / 入口锚点房间共享边界
- 复用 `shared_boundary_between`

### 2.2 修补尝试

对每个几何邻居 `N`（`N.category != "private"`，且非 stair/void/circ）：

1. 共享边长度 `L >= min_corridor_width * 1.5`
2. 从 `N` 切出 0.9m 走廊条，`N` 收缩
3. 校验：`N` 面积 ≥ min_area、长宽比 ≤ threshold、新走廊接入循环网络
4. 湿区 donor 优先；每层最多 1 次；`direct_circ_touch_only` 模式用于二次直连尝试

### 2.3 修补后处理

- `resolve_placement_overlaps`
- `apply_corridor_access_repair_if_safe` 门控完整 checker
- 只跑一轮，不迭代

---

## 3. 管线位置

```
… → assign_residual_gaps_as_circulation
  → resolve_exterior_entry
  → apply_corridor_access_repair_if_safe   ← checker 门控
```

（在 `guillotine.py` 中于 `resolve_exterior_entry` 之后调用，以便拿到入口锚点。）

---

## 4. RealizedAccessGraph 补充

`access.py`：

- `_add_circulation_corridor_passages`：可通行 `circ-*` 与 program 房间 PASSAGE
- `_add_circulation_fragment_links`：相邻走廊碎片互连

---

## 5. 隐私指标

`evaluation/privacy.py`：

- `_preferred_path_for_private`：优先不经其它卧室
- `unavoidable_private_through_count`：无替代路径时才计为结构不可避免

---

## 6. 测试

| 文件 | 覆盖 |
|------|------|
| `test_corridor_access_repair.py` | 单元：借边、跳过、孤岛走廊、楼梯不作 donor |
| `test_corridor_repair_integration.py` | valid_ratio、Top-5 ≤50%、unavoidable、PASSAGE |
| `test_access.py` | circ PASSAGE 单元 |

---

## 7. 非目标

- 不追求 100% 消除链式穿越
- 不解决走廊碎片形状
- 不改变门连接 Rule 1/2
- 不涉及「走廊先行切分」

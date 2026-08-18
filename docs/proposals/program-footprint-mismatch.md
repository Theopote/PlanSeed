# Proposal — Program/Footprint Area Mismatch Advisory

> **状态：Implemented（2026-08-18）。** 对应 [ADR-012](../adr/012-program-footprint-mismatch-advisory.md)。

---

## 1. 数据支撑

benchmark_program() 实测：

| 层 | 房间目标合计 | 可建面积 | 粗算缺口 (footprint − sum) |
|----|-------------|----------|---------------------------|
| F1 | 59.0㎡ | 143.0㎡ | 84.0㎡ |
| F2 | 60.0㎡ | 143.0㎡ | 83.0㎡ |

公式 surplus（扣楼梯核 + 15% 走廊预留）约 55㎡/层，surplus_ratio ≈ 38%。

---

## 2. 公式

```
footprint = buildable.width × buildable.depth
reserved  = 楼梯核 + ATRIUM 等预扣除 void（每层）
program_sum = Σ room.target_area（该层）
circulation_allowance = footprint × 0.15
surplus = footprint - reserved - program_sum - circulation_allowance
```

`surplus_ratio > 0.3` → advisory finding。

---

## 3. 接入

`run_pipeline` 生成前 `check_program_footprint_fit(program)` 一次；
结果并入各 valid 候选 `evaluation.findings`。

---

## 4. 测试

`solver/tests/test_program_footprint_advisory.py`

---

## 5. 非目标

- 不自动加天井 / 缩地 / 增房间
- 不限制走廊面积
- 不做前端一键采纳

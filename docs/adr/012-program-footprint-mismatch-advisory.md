# ADR-012 — Program/Footprint Area Mismatch Advisory

## Status

**Implemented**（2026-08-18）。`check_program_footprint_fit` 在 pipeline 生成前算一次，
advisory finding 复用到各候选 evaluation。

## Context

同一根因（房间需求远小于可建面积）反复表现为不同症状：卫生间超标、次卧/书房撞上限、
穿卧室路径、走廊膨胀到 17㎡。benchmark F1/F2 房间目标合计 59–60㎡，可建 143㎡，
粗算缺口 83–84㎡。

## Decision

在 `solver/program/normalize.py` 新增一次性静态检测 `check_program_footprint_fit`：

```
surplus = footprint - reserved - program_sum - circulation_allowance
surplus_ratio = surplus / footprint
```

- `circulation_allowance_ratio` 默认 15%
- `surplus_ratio_threshold` 默认 30%
- `reserved` = 楼梯核 + 用户声明的 ATRIUM（预扣除 void）
- 超阈值 → `program.footprint_underfilled:{floor_id}` WARNING finding
- 不阻断生成、不修改输入

## Implementation

- `solver/pipeline.py`：生成前调用一次，合并进 valid 候选的 `evaluation.findings`
- 测试：`solver/tests/test_program_footprint_advisory.py`

## Consequences

- 纯输入层 advisory，不碰生成器几何
- 不自动执行建议（加天井 / 缩地 / 增房间）
- 阈值 15%/30% 为经验值，待多 benchmark 校准
- 用户不采纳建议时，走廊膨胀等问题仍会存在——提升可解释性而非自动修复

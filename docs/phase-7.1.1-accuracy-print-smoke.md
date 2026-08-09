# Phase 7.1.1 — Presentation Accuracy & Print Smoke

> **性质：极短收口**（不插新大阶段；完成后立刻 7.2）  
> **总路线：** 7.1.1 → **7.2 Export** → **7.5 Alpha Hardening** → **8.0 Solver 2.0**  
> 打印：[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md) · 总览：[phase-7-deliverables.md](phase-7-deliverables.md)

## 不做

- 重开 Phase 6 · 重构 Solver · Shapely / CP-SAT / GA  
- 全面 strict mypy · OpenAPI 大扫除 · 持久化大改（→ **7.5**）  
- 每发现一个问题就新开 Phase

---

## 7.1.1-A — 北向系统（P0）✅ Engineering

**错误做法：** HTML 自己读 `site.north_angle` 猜变换；或 unknown → 默认 0° 画假 ▲N。

**正确链路：**

```text
SiteCoordinateSystem / requirement.site.north_angle
        ↓ resolve_north_angle_deg（仅 report_builder）
FloorPlanBlock
  ├─ svg
  ├─ north_angle_deg
  └─ orientation_defined
        ↓
Report HTML（只 rotate 或「北向未定义」）
```

| 规则 | 行为 |
|------|------|
| `north_angle` 已知（含 0） | 显示北针 + `rotate(-angle)` |
| 显式 `null` / 缺键且无 assumption | **不**画北针；「北向未定义」 |
| `SiteCoordinateSystem.from_site` 默认 0 | **禁止**当「已知正北」 |

落点：`report.py` · `report_orientation.py` · `report_builder.py` · `report_html.py`

测试：

- `test_report_north_angle_zero`
- `test_report_north_angle_90`
- `test_report_north_angle_135`
- `test_report_north_unknown_not_fake`

**验收：** 报告中任何 ▲N 必须来自 `FloorPlanBlock.north_angle_deg`，不得由 renderer 发明。

---

## 7.1.1-B — RequirementSpec TS fidelity（P1）✅

**风险：** 手写 `RequirementSpecPayload` 瘦于 Python → Save/Reload 丢 `priority` / `source` / `north_angle`。

**本任务范围：** 仅 Python `RequirementSpec` ↔ TS `RequirementSpecPayload` 字段核对 + round-trip。  
**不做：** OpenAPI codegen。

| 字段 | 结论 |
|------|------|
| `site.north_angle` / `entrance_edge` / `road_edges` / `setbacks` | ✅ TS 已有 |
| `assumptions[].source` | ✅ + `cloneAssumptionPayload` |
| `unknowns[].priority` | ✅ + `cloneUnknownPayload` |
| `spaces[].preferred_orientation` / `floor_preference` / `min_width` | ✅ |
| `relation_intents` | ✅ |

**契约 fixture：** [`fixtures/requirement_spec_full.json`](../fixtures/requirement_spec_full.json)

| 侧 | 命令 |
|----|------|
| Python | `uv run pytest backend/tests/test_requirement_spec_fidelity.py`（含 project save/reload） |
| Desktop | `cd desktop && pnpm check:fidelity` |

危险模式（瘦 rebuild 丢语义）与正确 spread clone 均有测试锁定。

---

## 7.1.1-C — Windows WebView2 Print smoke（P1）☐

[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md) — Desktop Print → PDF 填表。  
**唯一剩余人手关门项。**

---

## Definition of Done

1. [x] 7.1.1-A 北向链路 + 四项测试  
2. [x] 7.1.1-B TS fidelity：共享 fixture + Python/TS 检查 + project save/reload  
3. [ ] 7.1.1-C Print smoke 结果表  
4. [x] 路线图含 7.2 → 7.5 → 8.0（优化建议进 7.5/8，不塞 7.2）

填完 C → **Phase 7.2 Export Formats**。

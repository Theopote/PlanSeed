# Phase 7.1.1 — Presentation Accuracy & Print Smoke

> **性质：极短收口**（可不升正式子阶段编号；落地后直接 7.2）  
> **前置：** 7.1 Report Presentation 工程完成  
> **总览：** [phase-7-deliverables.md](phase-7-deliverables.md) · 打印矩阵：[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md)

## 目标

7.1 视觉/结构已够 Alpha。本收口只堵 **准确性 + 真实打印**，不做品牌/主题/PDF 引擎。

| 级 | 项 | 状态 |
|----|-----|------|
| **P0** | North orientation correctness | ✅ Engineering（测试锁定） |
| **P1** | RequirementSpec TS fidelity audit | ✅ Engineering（类型 + 克隆路径审计） |
| **P1** | Windows WebView2 print smoke | ☐ **人手填表**（关门） |
| **P2** | 文档示例同步 | ✅ 本页 + 7.2 规划已对齐 |

完成后 → **Phase 7.2 Export Formats**（先 7.2.1 SVG）。

---

## P0 — North orientation

**规则：**

- `FloorPlanBlock.north_angle_deg` ← `resolve_north_angle_deg(requirement_spec)`  
- 来源：`site.north_angle`（含 `0`）或 assumption `site.north_angle`  
- **显式 `null` / 缺键且无 assumption → 未知** → HTML「北向未定义」，**禁止**画默认 ↑N  
- CSS：`rotate(-north_angle)`；与 `SiteCoordinateSystem` 一致

**证据：**

- `backend/services/report_orientation.py`
- `backend/tests/test_report_layer.py::test_north_angle_rotates_compass_and_unknown_omits_fake_n`
- Fixture：`debug/print-smoke/12_locale_zh.html`（有角）· `13_north_undefined.html`（未知）

**不做：** 重新解释坐标系；假默认北针；物理指北校准。

---

## P1 — RequirementSpec TS fidelity

**风险：** 瘦 `.map()` / `{ key, description }` 重建 → Save → Report 丢 `priority` / `source` → Cover 无 blocking。

**对照：** `packages/schema/requirements.py` ↔ `desktop/src/api/client.ts`

| 字段 | 结论 |
|------|------|
| `assumptions[].source` | `AssumptionPayload` + `cloneAssumptionPayload`；编辑用 `{ ...a, value, reason }` |
| `unknowns[].priority` | `UnknownPayload` + `cloneUnknownPayload`；Gaps 展示 blocking |
| `relation_intents` | `RelationIntentPayload` 完整 |
| `spaces` sync | `syncRequirementSpacesFromProgram` 用 spread |
| `site.north_angle` | `RequirementSpecPayload.site.north_angle`；可为 `null` |

**审计落点注释：** `client.ts`「TS Fidelity Audit」表；Gaps：`RequirementGapsPanel.tsx`。  
详补：[phase-5.1.1-program-fidelity.md](phase-5.1.1-program-fidelity.md)#TS-Fidelity-Audit。

---

## P1 — Windows WebView2 print smoke

**CSS ≠ 验收。** 必须：

Desktop → 报告 Print → **Microsoft Print to PDF**  
矩阵与结果表：[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md)

```powershell
uv run python scripts/generate_print_smoke_reports.py
# → debug/print-smoke/index.html
```

最少跑通：**1F / 2F / 3F** 分页；其余场景按表勾选。

---

## P2 — 文档

- 路线图阶段判断含 7.1.1  
- 7.2 子阶段按交付信任边界重写（SVG 三分 · PNG 光栅 · DesignReport JSON · Print polish 非引擎）  
- `generated_at` → `report_generated_at` **仍后置**（不挡 7.2）

---

## Definition of Done（7.1.1）

1. [x] 北针：已知旋转 / 未知不画假针（pytest）  
2. [x] TS fidelity：priority / source / north_angle 路径审计通过  
3. [ ] Print smoke 结果表填完（Desktop WebView2）  
4. [x] 7.2 规划写入 deliverables（无 ZIP / 无 PDF engine / 无 Canva）

**第 3 条是唯一剩余人手关门项。** 填完即可勾 7.1/7.1.1 关闭并开工 7.2.1。

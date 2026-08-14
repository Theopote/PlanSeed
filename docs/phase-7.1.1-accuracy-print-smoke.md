# Phase 7.1.1 — Presentation Accuracy & Print Smoke

> **极短收口。** 完成后关闭 **7.1**，立刻 **7.2**。不要继续美化。  
> 打印：[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md) · 总览：[phase-7-deliverables.md](phase-7-deliverables.md)

## 不做

重开 Phase 6 · Solver 重构 · OpenAPI · 截图 diff · 品牌/主题 · 每发现问题新开 Phase。

---

### 7.1.1-A — 北向 ✅

`FloorPlanBlock.north_angle_deg` + `orientation_defined` ← builder；HTML 只消费。  
未知不画假 ▲N。测试：`zero` / `90` / `135` / `unknown_not_fake`。

### 7.1.1-B — RequirementSpec TS fidelity ✅

`fixtures/requirement_spec_full.json` + pytest + `pnpm check:fidelity`。  
含 `priority` / `source` / `north_angle` / `relation_intents`；禁止瘦 map。

### 7.1.1-C — Windows WebView2 打印 smoke ✅

P02/P06 · Desktop · Microsoft Print to PDF · 2026-08-14。  
见 [phase-7.1-print-smoke.md](phase-7.1-print-smoke.md)。

### 7.1.1-D — 文档同步 ✅

Phase 7 文档 Key Intent 示例改为当前 **zh-CN** 真实输出：

```text
两层住宅
3 间卧室
客厅朝南
厨房靠近餐厅
```

禁止再写：`Two-story residence` / `3 bedrooms` / `Kitchen near dining`。

---

## Definition of Done（仅此四条）

- [x] 北向真实绑定项目坐标  
- [x] RequirementSpec TS fidelity audit 完成  
- [x] Windows WebView2 打印 smoke 完成（P02/P06 · 2026-08-14）  
- [x] 文档同步  

四条齐 → **7.1.1 ✅ 关闭**（随 Alpha v0.1.0 发布）。

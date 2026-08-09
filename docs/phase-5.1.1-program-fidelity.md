# Phase 5.1.1 — Program Fidelity Gate

> **状态：✅ P0 已收口**  
> 前置：[phase-5.1-revision-integrity.md](phase-5.1-revision-integrity.md)  
> 总览：[roadmap.md](roadmap.md)

## 目标

在接 Ollama / Phase 6 之前，保证：

1. **意图事实不丢失** — `RequirementSpec` 是持久化与再求解的事实源。  
2. **Revalidate 评价当前几何** — 楼梯 metadata 从 placements 推导。

## 已交付

| 项 | 实现 |
|----|------|
| Canonical spec | `GenerateResponse.requirement_spec`（ensure_spaces 后） |
| 项目持久化 | `ProjectPayload.requirement_spec` |
| Desktop 会话 | `requirementSpec` state；mutate / revalidate / regenerate 原样回传（+ Program 面积补丁） |
| Stair derive | `derive_stair_core_from_placements`；缺 metadata 不得默认满分 |
| Client preview | `geometryMutation.ts` 标注 NON-AUTHORITATIVE |

## 流程

```text
Generate → requirement_spec + program_summary + candidates
Save/Load → requirement_spec 往返
Edit room area → sync spaces in requirement_spec
Mutation / Revalidate → POST requirements = canonical spec
hydrate → stair_* from stair-* placements → evaluate
```

## 明确延后

- RealizedWetStack 从湿区 placements 推导（可与 Phase 6 同期）
- `base_generator_version` vs revision_source 拆分

## Definition of Done

均已满足。下一：**Phase 6 Local LLM**。

---

## TS Fidelity Audit（Phase 7.1.1-B；✅ + fixture 锁定）

**风险类同 5.1.1：** frontend 用瘦 schema / 瘦 `.map()` 重建对象 → Save → Report 时语义静默丢失  
（例如 `unknown.priority` 丢失 → Cover 不再显示 blocking）。

对照：`packages/schema/requirements.py` ↔ `desktop/src/api/client.ts` `RequirementSpecPayload`。

**共享 fixture：** [`fixtures/requirement_spec_full.json`](../fixtures/requirement_spec_full.json)  
**测试：** `backend/tests/test_requirement_spec_fidelity.py` · `desktop` → `pnpm check:fidelity`

| 字段 | 要求 | 7.1.1-B |
|------|------|---------|
| `assumptions[].source` | 保留；编辑时 `{ ...a, value, reason }` | ✅ |
| `unknowns[].priority` | 保留；禁止 `{ key, description }` 重建 | ✅ |
| `relation_intents` | TS 类型完整；往返不得丢 | ✅ |
| `spaces[].preferred_orientation` / `floor_preference` / `min_width` / `tags` | sync 用 spread | ✅ |
| `site.north_angle` / `entrance_edge` / `road_edges` / `setbacks` | 报告北针与场地语义 | ✅ |

**规则：** 复制子行只用 spread / `cloneUnknownPayload` / `cloneAssumptionPayload`。  
`fallbackRequirementFromForm(program)` 须带回 `program.assumptions` / `unknowns`。  
总收口：[phase-7.1.1-accuracy-print-smoke.md](phase-7.1.1-accuracy-print-smoke.md)。  
**不做**本任务顺手 OpenAPI。

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
| Stair derive | `derive_stair_core_from_placements` in `solver/mutation/commit.py` |
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

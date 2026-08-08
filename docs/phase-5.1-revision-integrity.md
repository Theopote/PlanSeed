# Phase 5.1 — Revision Integrity & Mutation Single Source

> **状态：✅ P0 已收口**  
> 总览：[roadmap.md](roadmap.md)

## 目标

> 让每一个显示的分数、finding、opening、access、已保存项目与已编辑几何，都指向同一套设计 revision。

## 已交付

| 项 | 实现 |
|----|------|
| Mutation 单源 | `POST /api/mutations/preview` → `preview_mutation()` |
| TS 降级 | `geometryMutation.ts` 仅 visual / 手柄 / 文案 |
| Dirty state | `revision_status=dirty`；Strip/Inspector 不展示旧分当当前 |
| Revalidate | `POST /api/mutations/revalidate` → openings + access + evaluate（不经 Guillotine） |
| 版本语义 | Save 保留 snapshot `schema_versions`；`project_meta` 单独戳 app |
| 持久化 | dirty + `mutations[]` 可存可开 |

## 流程

```text
drag (visual)
  → pointer-up → /mutations/preview
  → ok? commit placements + dirty + mutations[]
  → Revalidate → /mutations/revalidate
  → validated CandidatePayload（新 svg / score / validation）
```

## 明确延后

- 完整 DesignRevision 事件溯源树 UI
- Tauri 注入 `PLANSEED_DB`
- 增量局部重算（当前为全量 hydrate + checker + evaluate）

## Definition of Done

均已满足（见路线图勾选）。下一：**Phase 6 Local LLM**。

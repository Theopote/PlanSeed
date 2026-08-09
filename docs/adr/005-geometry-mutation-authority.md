# ADR-005 — Geometry Mutation Authority

## Status

Accepted

## Context

Workbench 直接改矩形若绕过校验与 lineage，会造成「看起来改了、再生成又丢」或非法几何。

## Decision

几何变更以权威 mutation / lock / regenerate 路径为准：预览 → 校验 → commit；Room Lock 等钉死矩形由 generator 尊重。  
禁止 UI 私自改 placement 却不走契约。

## Consequences

- `LayoutLocks` + revision integrity  
- Regenerate / mutation 测试覆盖 lock 不变量

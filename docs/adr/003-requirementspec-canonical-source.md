# ADR-003 — RequirementSpec is the canonical requirement source

## Status

Accepted

## Context

表单、NL 解析、假设与未知项若多源并存，UI 与 Solver 会对「需求是什么」产生分歧。

## Decision

`RequirementSpec` 是需求权威源。表单与 NL 都写入 / 合并到 Spec；normalize 后才得到 `DesignProgram`。  
Assumption / Unknown 可追踪，不可静默丢弃。

## Consequences

- API 与桌面以 Spec 同步为准（见 program fidelity）  
- Solver 只消费 Program，不回头猜 NL

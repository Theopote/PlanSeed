# ADR-002 — LLM never generates geometry

## Status

Accepted

## Context

若 LLM 直接输出房间坐标或 `DesignProgram` 几何，结果不可复现、难校验，且破坏 Solver 确定性。

## Decision

NL → `RequirementSpec` 仅经 **Hybrid Semantic Parser**（Local LLM + 确定性抽取 + Vocab + Gate + Repair）。  
LLM **不**直接输出 `DesignProgram` 或坐标；几何只由 Solver packing / mutation 产生。

## Consequences

- Prompt 保持短；靠 Benchmark→失败模式迭代，禁止堆 few-shot 冒充可靠  
- Solver / Evaluator / Renderer 分层不变

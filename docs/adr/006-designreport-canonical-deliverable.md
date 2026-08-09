# ADR-006 — DesignReport is the canonical deliverable

## Status

Accepted

## Context

导出若直接倾倒内部 Project Snapshot，用户会把调试态当成交付物，易误导。

## Decision

对外交付物以 `DesignReport` 为权威模型；HTML / Print / SVG / PNG / JSON 报告均由此派生。  
Project Snapshot ≠ DesignReport。

## Consequences

- Phase 7 交付层边界清晰  
- 报告须标明几何来源、假设与未知，避免「假合规」话术

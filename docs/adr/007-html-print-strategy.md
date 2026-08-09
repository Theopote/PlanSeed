# ADR-007 — HTML Print strategy

## Status

Accepted

## Context

自研 PDF 排版成本高，且与浏览器打印能力重复。

## Decision

Alpha / Phase 7：**HTML → 系统 Print（含另存 PDF）**，不自研完整 PDF 引擎。  
打印样式与屏幕预览同源 HTML，靠 CSS `@media print` 收口。

## Consequences

- 依赖浏览器打印质量；Print smoke 需手测勾选  
- 将来若要「纯服务端 PDF」，另开 ADR，不偷偷塞进 solver

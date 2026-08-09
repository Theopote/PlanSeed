# ADR-004 — Adjacency ≠ Access Intent

## Status

Accepted

## Context

「相邻」与「必须可达 / 门连接」常被混用，导致拓扑与硬约束语义漂移。

## Decision

- **Adjacency**：空间关系偏好（可软可硬，视约束种类）  
- **Access**：通行意图（AccessGraph / Connection / 开门）  

两者分模型、分校验；禁止用 adjacency 冒充 access。

## Consequences

- Schema 与 checker 分轨  
- UI / 报告解释必须区分「挨着」与「走得通」

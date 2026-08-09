# ADR-001 — Local-first

## Status

Accepted

## Context

PlanSeed 是独栋住宅生成式设计工具。云端 LLM / 远程推理会破坏隐私预期与离线可用性。

## Decision

默认所有推理与求解在本机完成：SQLite、本机 Ollama（loopback）、本地 FastAPI sidecar、Tauri desktop。  
非 loopback Ollama 须显式 `PLANSEED_OLLAMA_ALLOW_REMOTE=1`，并警示用户。

## Consequences

- 禁止默认依赖云端 LLM API  
- 打包与 Alpha 交付以 Windows 本机为先  
- 远程模型永远不是「悄悄可用」

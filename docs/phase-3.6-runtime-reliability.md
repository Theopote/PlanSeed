# Phase 3.6 — Desktop Runtime Reliability & Evaluation Contract

> **← 当前短周期**（在 3.5 Core Consolidation 之上收口「真能双击用」）  
> 目标：本地引擎、评分单一事实源、比较逻辑、测试与发布链做稳。  
> **不做**：LLM、推倒四区 UI、继续扩 solver feature。

配套总览见 [roadmap.md](roadmap.md)。

---

## 已确认正确（3.5 遗产，本阶段勿回退）

```text
generate → validate → evaluate → candidate.evaluation → rank
```

- API **禁止**重评 / 自创评分架构；只序列化 `evaluation`
- 七轴：Program / Spatial / Circulation / Privacy / Environment / Technical / Robustness
- Metric Ownership：原始 metric 单主归属
- DesignFinding：severity / room_ids / metric / recommended_action

---

## P0 — 引擎身份与端口契约

| 项 | 状态 |
|----|------|
| 复用端口前必须 `GET /api/health` 且 `ok` + `service=planseed` | ✅ |
| 8787 被外来进程占用 → **换端口自启**，不得误 reuse | ✅ |
| 就绪探测用 health，而非仅 TCP `connect` | ✅ |
| setup 不阻塞；`engine-ready` 异步通知 | ✅（3.5） |
| Windows onedir 真装包验收 | ❌ 仍待本机跑 |

错误路径（本阶段已堵）：

```text
任意 localhost:8787 TCP 开放
  → 误认 PlanSeed
  → ready=true 且永不 spawn
  → 前端 health 失败
```

正确路径：

```text
preferred 端口
  ├─ health=planseed → reuse
  ├─ 空闲 → bind + spawn
  └─ 被占用但非 PlanSeed → 另选端口 + spawn
```

---

## P1 — Evaluation / Compare 契约

| 项 | 要求 |
|----|------|
| 单一事实源 | `LayoutCandidate.evaluation` 是完整 DesignEvaluation |
| 确定性 | 同 program + seed → 同 geometry + 同 evaluation（含 findings 序） |
| Compare | 只吃 evaluation 差分；禁止 LLM |
| API | 响应 `design_score` 来自 evaluation，次数 = valid |

---

## P2 — 发布链（本短周期能推进多少算多少）

- [ ] `build_backend_sidecar` onedir → `tauri:build` Windows 冒烟
- [ ] 文档与 DoD 与代码一致
- [ ] CSP 仍属 Phase 5 Packaging，不在此强行严配

---

## Definition of Done（3.6）

1. 外来 8787 服务不会被当成 PlanSeed  
2. 自启后 health 轮询到 `service=planseed` 才 `ready`  
3. evaluation 契约测试保持绿  
4. Compare / Inspector 仍走 evaluation  
5. pytest + ruff + mypy（宽松）+ desktop tsc 绿  

下一阶段再回到 Desktop Workbench 加深或 Packaging。

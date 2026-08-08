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

## P0 — Engine Identity Probe

不要：`TCP open?`

必须：

```text
GET /api/health
→ {
    "ok": true,
    "service": "planseed",
    "api_version": "1",
    "engine_version": "0.1.0"
  }
```

Rust 三态：

| 身份 | 行为 |
|------|------|
| `PORT_FREE` | bind preferred（或失败则 ephemeral）+ spawn |
| `PLANSEED_ENGINE` | reuse |
| `FOREIGN_SERVICE` | **不要 reuse** → pick another port → launch PlanSeed |

就绪判定：**poll `/api/health` + identity/version**（应用级），不是 TCP listen。

端口占用：

```text
选 port → 立即 spawn → health 失败或进程退出 → 换 port 重试（最多 5 次）
```

不预占 `TcpListener` 再释放（避免 TOCTOU）；极小竞态由重试消化。

| 项 | 状态 |
|----|------|
| health 含 api_version / engine_version | ✅ |
| 三态探针 PORT_FREE / PLANSEED_ENGINE / FOREIGN_SERVICE | ✅ |
| FOREIGN → 换端口自启 | ✅ |
| `probe_engine` / `wait_for_engine`（非 port_open / wait_for_port） | ✅ |
| spawn 失败 / health 超时 → 换端口重试 | ✅ |
| setup 不阻塞；`engine-ready` 异步通知 | ✅ |
| Windows onedir 真装包验收 | ❌ 仍待本机跑 |
---

## P1 — Evaluation / Compare 契约

| 项 | 要求 |
|----|------|
| 单一事实源 | `LayoutCandidate.evaluation` 是完整 DesignEvaluation |
| 确定性 | 同 program + seed → 同 geometry + 同 evaluation（含 findings 序） |
| Compare | 只吃 evaluation 差分；禁止 LLM |
| API | 响应 `design_score` 来自 evaluation，次数 = valid |

---

## P2 — 发布链（resources 路线，不回退 externalBin）

- [x] 锁定：`bundle.resources` + onedir + managed `Command`（**不做 externalBin**）
- [x] 正式 `sidecar_path` 仅 canonical：`{resource_dir}/planseed-backend/<exe>`
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

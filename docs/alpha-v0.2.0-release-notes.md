# Alpha v0.2.0 — Release Notes

> Architect Workflow / AI Design Copilot 首发 Alpha · solver **0.6**  
> Tag：`v0.2.0-alpha` · 安装包：`PlanSeed_0.2.0_x64-setup.exe`

## PlanSeed Alpha v0.2.0

**平台：** Windows 10/11 x64 only

### 安装

1. 下载 `PlanSeed_0.2.0_x64-setup.exe`
2. 运行安装程序
3. 启动 **PlanSeed**，等待引擎 **已就绪**

### 相对 v0.1.1 的变更

- **AI Design Copilot 数据闭环** — Intent Patch → Spec 同步 → Critique / Optimize / Strategies / Conversation
- **`candidate_rebuild`** — API `CandidatePayload` ↔ solver `LayoutCandidate` 受控重建
- **Optimize 尊重用户锁**；可选 `project_id` 回落候选
- **Intent Hybrid** — 确定性抽取 + 可选本地 Ollama 草稿（失败回退）
- Desktop Copilot 面板 + 项目快照中的 `design_conversation`
- 详见 [copilot.md](copilot.md) · [v0.2-architect-workflow.md](v0.2-architect-workflow.md)

### Alpha Stable 默认（未变）

Guillotine + axis-diverse + heuristic + rect + residential-alpha-v1

### Known limitations

- Copilot 为早期 Alpha；Design Benchmark v2 **ab_rate** 仍依赖人工复评
- 产品默认 geometry 仍为 **rect**；irregular site 为 engineering-only
- MaxRect / Pareto / CP-SAT — experimental only
- 自然语言解析建议安装本地 [Ollama](https://ollama.com)（可选）
- 非规范合规 · 非施工图交付

### 冒烟

```powershell
powershell -File scripts/windows_alpha_smoke.ps1
powershell -File scripts/installer_release_smoke.ps1
```

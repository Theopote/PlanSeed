# Alpha v0.1 Release Readiness

> **这是 Release Gate，不是 Phase 9。**  
> 目标一句话：**在稳定默认配置下，证明现有能力可以交给用户。**  
> 总览：[roadmap.md](roadmap.md) · **最短手测**：[alpha-v0.1-hand-smoke.md](alpha-v0.1-hand-smoke.md) · 稳定化：[phases/phase-8.5-alpha-stabilization.md](phases/phase-8.5-alpha-stabilization.md)

## 当前状态判断

```text
0–7.5     Product + Engineering Core     ✅
8.0-A/B   Multi-generator foundation     ✅ Engineering
8.1       Diversity（Alpha 默认）         ✅
8.2       Pareto                         ✅ Engineering / Experimental
8.3       CP-SAT                         ✅ Engineering / Experimental
8.4       Irregular Geometry Foundation  ✅（非端到端）
8.4.1     Irregular Site Pipeline        ☐（Post-v0.1 backlog）

Alpha v0.1 Release Qualification         ← CURRENT（核心语义已再冻结）
```

### 核心语义冻结（Release Gate 期间）

**只允许**：bugfix · security · packaging · validation correctness · release regression。

**禁止继续扩面**（进入 Post-v0.1 backlog）：

- 新 parser policy / Unknown 策略变更（须重跑 Blind qualification）
- 新 constraint 语义 / solver 特性
- 8.4.1 irregular site · Phase 9

**Release Gate 前已修正的语义回归**（`d6628a2` 及同批）：

| 项 | 修正 |
|----|------|
| SeparationConstraint | 同层平面分离；跨层 `not applicable` |
| AccessConstraint `requires_stair_reach` | 移除 `has_stair` 启发式；上层可达统一走 RealizedAccessGraph |
| LLM `llm_inference` | 不进 canonical assumptions/unknowns；记入 `parser_audit.discarded_inferences` |

自动化回归：`powershell -File scripts/alpha_release_gate_automated.ps1`（不含 WebView2 Print / 安装包手测）。

| 概念 | 含义 |
|------|------|
| Engineering Complete | 有实现 + 有测试 + 文档勾过 |
| Product Qualified | 默认路径 / 安装包 / 手测冒烟通过 |
| Product Default Ready | 可写入 Alpha Stable profile |

**MaxRect / Pareto / Irregular Geometry** 今日多为前者，尚未后者。

## Alpha Stable（产品默认 · 冻结）

| 层 | 值 |
|----|-----|
| Generator | `guillotine` |
| Selection | `axis`（axis-diverse） |
| Assignment | `heuristic` |
| Geometry | `rect` |
| Evaluation | `residential-alpha-v1` |
| Profile id | `alpha-stable` |

代码：`packages.schema.solver_profile.ALPHA_STABLE` · API `generate_layouts` 对非 `experimental` 配置执行 `pin_alpha_stable_if_needed`。

## Experimental Solver Lab（opt-in only）

| 能力 | 进入方式 |
|------|----------|
| MaxRect | `experimental=True` + `generator_strategy="maxrect"` 或显式 `generators=` |
| Pareto | `experimental=True` + `rank_mode="pareto"`（或 `research-pareto` profile） |
| CP-SAT | research 依赖组 + assignment profile（不进 Alpha runtime） |
| Shapely | 8.4 工具层；**不得**宣称端到端 irregular-site |

禁止：研究功能静默改变产品默认行为。

## Gate 清单

### 1. 稳定默认路径

- [x] `rank_mode` 默认 `"axis"`（非 Pareto）
- [x] `generator_strategy` 默认 `"guillotine"`
- [x] `SolverProfile` + Alpha Stable / Research 预设
- [x] 产品路径 pin：非 experimental → Alpha Stable
- [x] Solver provenance / `SOLVER_VERSION=0.5` / selection 版本化

### 2. Regression（同 seed + 同 profile → 同结果）

自动化（含 profile pin / axis Top-K / quality / locks / mutation / report·export API / `.planseed` 单元）：

- [x] generation regression（默认 Guillotine + axis）
- [x] locks regression
- [x] mutation regression
- [x] report regression
- [x] save/load · `.planseed` 单元往返（完整手测仍见 §5）
- [x] export regression（SVG/PNG/JSON API）
- [x] **语义修正后重跑**（`d6628a2`：Separation / Access / parser audit）— `scripts/alpha_release_gate_automated.ps1`

仍须产品手测勾选：Print / 安装包 / 完整 `.planseed` 场景（§3–5）。

### 3. Windows WebView2 Print Smoke（7.1.1）

- [ ] 真实 Windows 桌面：打开报告 → Print → 预览/出纸无空白、无裁切灾难  
  最短步骤：[alpha-v0.1-hand-smoke.md](alpha-v0.1-hand-smoke.md) §A · 详表：[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md)

### 4. 安装包 Smoke

尤其 `resvg-py` / Pillow 进入正式依赖后：

- [ ] PyInstaller sidecar 能启动（`build_backend_sidecar.ps1` 已 `--collect-all resvg_py`）
- [ ] Windows release bundle 安装可运行
- [ ] PNG export / SVG export / report 在**安装包**环境验证（`scripts/alpha_release_engine_smoke.py`）
- [ ]（可选）Ollama

最短步骤：[alpha-v0.1-hand-smoke.md](alpha-v0.1-hand-smoke.md) §B

### 5. `.planseed` 完整往返

- [x] API 保真单测：`test_planseed_full_fidelity_roundtrip`（RequirementSpec / Program / Candidates / revision / locks / mutations / provenance）
- [ ] Desktop 场景手测（导出 → 删本地 → 导入 → 报告 / SVG·PNG）  
  最短步骤：[alpha-v0.1-hand-smoke.md](alpha-v0.1-hand-smoke.md) §C
- [ ] **不**在本 Gate 扩格式

### 6. 明确不做（本 Gate）

- Phase 9 / Advanced AI / BIM / Code Compliance 扩面
- 更多算法主线
- MaxRect 混入 Alpha 默认候选池
- 宣称 irregular-site 产品支持（待 8.4.1）

## 优先级（与本 Gate 对齐）

| 级 | 项 |
|----|-----|
| **P0** | 默认回稳（已落地）· selection provenance（已落地）· Solver regression 重跑 · Print Smoke |
| **P1** | Benchmark 扩到 10–12 案（Suite v1 已有骨架）· MaxRect 保持 experimental · `.planseed` roundtrip · 安装包 PNG/export |
| **P2** | 8.4.1 polygon pipeline · 各向退线精确算法 |

## 通过标准

全部 **Gate 清单 1–5** 勾完，且 Alpha Stable 下无已知「默认行为与文档不符」的 P0，方可称 **Alpha v0.1 Release Ready**。  
勾选前不得把 roadmap 主线标成 Phase 9。

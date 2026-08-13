# Alpha v0.1 — 最短手测清单（Release Gate）

> **不是新功能。** 只验证现有能力能否交给用户。  
> Gate 总览：[alpha-v0.1-release-readiness.md](alpha-v0.1-release-readiness.md)  
> 详细 Print 矩阵：[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md) · 装包基线：[windows-alpha-smoke.md](windows-alpha-smoke.md)

默认产品路径须为 **Alpha Stable**：Guillotine · axis · heuristic · rect · residential-alpha-v1。

---

## A. Windows WebView2 Print（7.1.1 · 必过）

```powershell
uv run python scripts/generate_print_smoke_reports.py
# 对照可参考 Edge；关门必须在 Desktop 报告预览 → Print → Microsoft Print to PDF
```

| # | 动作 | Pass |
|---|------|------|
| A1 | Desktop 打开任意完整报告 → Print → **Microsoft Print to PDF** · A4 纵向 | ☐ |
| A2 | 封面 / 目录不被截断；平面 SVG 不被跨页切开 | ☐ |
| A3 | 中文不方框；P08（若测）英文字体正常 | ☐ |
| A4 | 至少抽测 **P02**（两层）+ **P06**（长 Findings）或等价真实项目 | ☐ |

全部 ☐→☑ 后勾 [phase-7.1.1-accuracy-print-smoke.md](phase-7.1.1-accuracy-print-smoke.md) DoD 第 3 条。

---

## B. 安装包 + resvg PNG（必过）

```powershell
uv sync --group build
pwsh scripts/build_backend_sidecar.ps1
# 需 Rust + pnpm：
pwsh scripts/build_installer.ps1
# 安装 NSIS setup → 启动 PlanSeed
pwsh scripts/windows_alpha_smoke.ps1
uv run python scripts/alpha_release_engine_smoke.py
# 装包引擎（PyInstaller onedir，无需 NSIS）：
powershell -File scripts/sidecar_release_smoke.ps1
# NSIS 静默安装 + 装包 sidecar smoke（Gate B3 半自动）：
powershell -File scripts/installer_release_smoke.ps1
# 预检工具链与产物：
powershell -File scripts/preflight_release_gate.ps1
# 或本地开发引擎已启动时一键跑自动化子集：
powershell -File scripts/alpha_release_gate_automated.ps1 -SkipPrintHtml
```

| # | 动作 | Pass |
|---|------|------|
| B1 | 安装包启动 → 引擎 **已就绪**（非仅开发 `uv run`） | ☐ |
| B2 | `windows_alpha_smoke.ps1`：health + generate + compare | ☐ |
| B3 | `sidecar_release_smoke.ps1` / `installer_release_smoke.ps1`：Alpha Stable + PNG + SVG + report + `.planseed` | ☐（脚本可自动化；装包须 rebuild 后勾） |
| B4 |（可选）Ollama 解析一条短需求；失败只记备注，不挡 Gate 除非宣称 LLM 必过 | ☐ |

---

## C. `.planseed` 完整往返（必过）

自动化已有 API 保真单测；本表是 **Desktop 场景**：

| # | 动作 | Pass |
|---|------|------|
| C1 | 项目 A：生成 → 锁一间房 → 可选 nudge → 选中候选 → **导出 .planseed** | ☐ |
| C2 | 删除本地项目（或换机）→ **导入** 同文件 | ☐ |
| C3 | 检视：RequirementSpec / Program / Candidates / revision / locks / mutations / provenance | ☐ |
| C4 | 报告可打开；再导出 SVG 或 PNG 一次成功 | ☐ |
| C5 | **不**改包格式、不扩字段 | ☐ |

---

## 勾完后

把本页 A/B/C 全部 ☑ → 回写 [alpha-v0.1-release-readiness.md](alpha-v0.1-release-readiness.md) §3–5 → 才可称 **Alpha v0.1 Release Ready**。  
在此之前 **禁止** 开 Phase 9 / Advanced AI / BIM / Code 扩面。

# LLM Alpha Baselines

本目录存放 **真模型 Pipeline** Qualification 结果（Phase 6.7 / 6.7.1 / 6.7.2）。

## 生成

```powershell
ollama pull qwen2.5:7b

# 严格独立资格（默认 Blind）
.\scripts\run_llm_qualify.ps1 -Gate

# 已泄漏 Holdout（工程回归）
.\scripts\run_llm_qualify.ps1 -CaseSet holdout

# Development
.\scripts\run_llm_qualify.ps1 -CaseSet development
```

```bash
uv run python -m packages.llm.benchmark.qualify --gate
uv run python -m packages.llm.benchmark.qualify --set holdout
```

## 产物

| 文件 | 含义 |
|------|------|
| `llm-alpha-baseline.json` | **Blind + Pipeline** 最新一次（严格资格） |
| `llm-alpha-baseline-blind-v1.json` | Blind v1 归档（FAIL） |
| `llm-alpha-baseline-blind-v2.json` | Blind v2 归档（FAIL） |
| `llm-alpha-baseline-holdout-pipeline.json` | Holdout 工程回归 |
| `llm-alpha-baseline-<set>-<mode>[-model].json` | 其他组合 |

Blind / Holdout 默认**不写** per-case `failed_cases`（防逐案过拟合）。

**Strict Alpha Qualified** 仅当 Blind + Pipeline 的 `alpha_gate.passed` 为真。  
Holdout 过门 ≠ 严格独立泛化证据（见 phase-6.7.2）。

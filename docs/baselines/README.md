# LLM Alpha Baselines

本目录存放 **真模型 Pipeline** Qualification 结果（Phase 6.7 / 6.7.1）。

## 生成

```powershell
# 1. 启动 Ollama 并安装模型（须用户显式 pull，PlanSeed 不自动下载）
ollama pull qwen2.5:7b

# 2. Holdout + Pipeline（默认）+ Alpha Gate
.\scripts\run_llm_qualify.ps1 -Gate

# Development 集（调规则；不作唯一证据）
.\scripts\run_llm_qualify.ps1 -CaseSet development

# 仅模型 Raw（enrich=False，诊断）
.\scripts\run_llm_qualify.ps1 -Mode model_raw

# 多模型对比
.\scripts\run_llm_qualify.ps1 -Models "qwen2.5:7b,<候选>" -Gate
```

等价：

```bash
uv run python -m packages.llm.benchmark.qualify --gate
uv run python -m packages.llm.benchmark.qualify --set development --mode pipeline
```

## 产物

| 文件 | 含义 |
|------|------|
| `llm-alpha-baseline.json` | **Holdout + Pipeline** summary + `alpha_gate` + meta |
| `llm-alpha-baseline-<set>-<mode>[-model].json` | 其他组合 |
| `llm-alpha-compare-*.json` | 多模型对照 |

Holdout 默认**不写** per-case `failed_cases`（防逐案过拟合）；需要时加 `-DetailFailed`。

**勿与 CI oracle 100% 混淆。** 仅当 **Holdout + Pipeline** 的 `alpha_gate.passed` 为真才可写 Phase 6 ✅ Alpha Qualified。

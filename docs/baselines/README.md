# LLM Alpha Baselines

本目录存放 **真模型** Qualification 结果（Phase 6.7）。

## 生成

```powershell
# 1. 启动 Ollama 并安装模型（须用户显式 pull，PlanSeed 不自动下载）
ollama pull qwen2.5:7b

# 2. 全量跑分 + Alpha Gate
.\scripts\run_llm_qualify.ps1 -Gate

# 或多模型对比（判断 7B 是否够用）
.\scripts\run_llm_qualify.ps1 -Models "qwen2.5:7b,<候选>" -Gate
```

等价：

```bash
uv run python -m packages.llm.benchmark.qualify --gate
```

## 产物

| 文件 | 含义 |
|------|------|
| `llm-alpha-baseline.json` | 单模型 summary + `alpha_gate` + 失败用例 |
| `llm-alpha-baseline-<model>.json` | 多模型时每模型一份 |
| `llm-alpha-compare.json` | 多模型对照 |

**勿与 CI oracle 100% 混淆。** 过 `alpha_gate.passed` 后才可写 Phase 6 ✅ Alpha Qualified。

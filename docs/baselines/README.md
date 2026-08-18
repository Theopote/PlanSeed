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
| `llm-alpha-baseline.json` | **Blind + Pipeline** 最新（v4 **工程 PASS**） |
| `llm-alpha-baseline-blind-v1.json` | Blind v1 归档（FAIL） |
| `llm-alpha-baseline-blind-v2.json` | Blind v2 归档（FAIL） |
| `llm-alpha-baseline-blind-v3.json` | Blind v3 归档（FAIL） |
| `llm-alpha-baseline-blind-v4.json` | Blind v4 归档（工程 PASS；严格可复现 ⚠） |
| `llm-alpha-baseline-holdout-pipeline.json` | Holdout 工程回归 |
| `llm-alpha-baseline-<set>-<mode>[-model].json` | 其他组合 |

Blind / Holdout 默认**不写** per-case `failed_cases`（防逐案过拟合）。

**Engineering Gate：** Blind + Pipeline 的 `alpha_gate.passed`。  
**冻结可复现（Strict）：** `--gate` 要求 `git status` clean；baseline 须 `meta.git_dirty=false`，且 case set / parser 文件已在该 `git_commit` 内。  
脏工作区 + `--gate` → `QualificationError`（exit 2），**拒绝跑分**，避免「未 commit 代码 + 旧 SHA」假证据。  
Blind v4 历史基线：`git_commit=c79c03fd` 但不含 blind-v4 → **工程资格 ✅ / 严格可复现 ⚠**（见 phase-6.7.2）。  
Holdout 过门 ≠ 严格独立泛化证据。
## Phase 6 post-alpha known limitations

不阻塞 Phase 7（详见 [hybrid-semantic-parser.md](../hybrid-semantic-parser.md)）：

- **Latency**：avg ~15–20s（进度文案；性能另阶段）
- **bathrooms**（Holdout 分字段 ≈87.5%）：整体 field 已高；卫浴为已知弱项，禁止逐案 regex 冒充修复


## Layout generation（Phase 8.0-C / Suite v1）

**单 case 不够资格判定。** 请用 Layout Benchmark Suite v1：

详案：[layout-benchmark-suite-v1.md](layout-benchmark-suite-v1.md)

```bash
uv run python -m solver.benchmark --suite v1 --count 32
uv run python -m solver.benchmark --suite v1 --count 64 \
  --out docs/baselines/layout_benchmark_suite_v1_n64.json

# 旧单 case（仅回归；≠ MaxRect 资格）
uv run python -m solver.benchmark --count 32
```

| 文件 | 含义 |
|------|------|
| `layout_generation_guillotine_vs_maxrect.json` | **遗留** 单 case（`benchmark_program` 含车库 · n=32 · **2026-08-09 硬约束前** · `valid_rate=1.0` 已过时） |
| `layout_benchmark_suite_v1_n32.json` | Suite v1 全量 B01–B12（n=32 · solver 0.6） |
| `layout_benchmark_suite_v1_n32_qualification.json` | 同上 + MaxRect gate 结论 |
| `layout_benchmark_suite_v1_n64.json` | Suite v1 全量 B01–B12（n=64 · solver 0.6） |
| `layout_benchmark_suite_v1_n64_qualification.json` | 同上 + MaxRect gate 结论 |

**资格判定（勿与「实现完成」混淆）：**

| Strategy | Implementation | Product qualified |
|----------|----------------|-------------------|
| Guillotine | ✅（Alpha 默认） | ✅（当前默认路径） |
| MaxRect | ✅ | **❌**（须过 Suite v1；单 case aspect penalty 已暴露劣化） |

MaxRect 仅 research / opt-in；禁止因「8.0-B ✅」写成产品已验收。

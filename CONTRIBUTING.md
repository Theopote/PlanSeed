# 贡献指南

感谢关注 PlanSeed。本仓库以 MIT 开源；欢迎通过 Issue 与 Pull Request 参与。

## 开发环境

- Python **3.12** + [uv](https://github.com/astral-sh/uv)
- 桌面端：Node.js + [pnpm](https://pnpm.io/)、可选 Rust（Tauri）
- 所有 Python 命令请用 `uv run`，不要混用系统 pip / poetry 等

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy packages solver backend
```

桌面端：

```bash
pnpm install
pnpm --dir desktop build
```

## 架构约定（请先读）

```text
RequirementSpec → normalize → DesignProgram → generate → LayoutCandidate
```

1. **严格分层**：Solver 纯 Python 确定性；Evaluator 只评分；Renderer 只渲染。
2. **输入输出分离**：RoomSpec（需求）与 RoomPlacement（solver 输出）不可混用。
3. **可复现**：相同 DesignProgram + seed 必须相同结果；禁止未注入的全局 `random`。
4. **NL 解析**：Hybrid Semantic Parser（Local LLM + 确定性抽取 + Vocabulary + Semantic Gate + Repair）；LLM 不直接输出 DesignProgram 或坐标。
5. **注释 / commit message**：中文；标识符：英文。

更多见 [docs/architecture.md](docs/architecture.md)、[docs/hybrid-semantic-parser.md](docs/hybrid-semantic-parser.md)。

## Pull Request

1. 从最新 `master` 开分支，主题尽量单一。
2. 附上动机与验证方式（相关测试 / 手工步骤）。
3. 确保本地 `uv run pytest` 与 `uv run ruff check .` 通过；改动到桌面端时跑 `pnpm --dir desktop build`。
4. 不要提交密钥、`.env`、构建产物、`node_modules`、sidecar 二进制。

## Issue

请尽量写清：期望行为、实际行为、复现步骤、环境（OS / Python / 是否 Tauri）。  
若与解析准确率相关，优先描述失败模式，而不是对着单条 Blind 扩 regex。

# PlanSeed

[![CI](https://github.com/Theopote/PlanSeed/actions/workflows/ci.yml/badge.svg)](https://github.com/Theopote/PlanSeed/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Theopote/PlanSeed?include_prereleases&label=Alpha)](https://github.com/Theopote/PlanSeed/releases/tag/v0.1.0-alpha)

Local-first、本地运行的独栋住宅生成式设计工具。

> AI understands the design intent.  
> The solver proves the geometry.  
> The evaluator explains the quality.  
> The architect remains in control.

**技术栈**：Python 3.12（uv）· FastAPI · Tauri v2 + React + TypeScript · Pydantic · SVG · SQLite  
**约束**：纯本地运行；禁止云端 LLM API / Electron / Three.js 平面图库。

## 当前版本

| 项 | 值 |
|----|-----|
| **Release** | **PlanSeed Alpha v0.1.0**（[`v0.1.0-alpha`](https://github.com/Theopote/PlanSeed/releases/tag/v0.1.0-alpha)） |
| **Platform** | Windows 10/11 x64 |
| **Status** | **Released**（2026-08-14） |
| **Next** | Post-v0.1 planning · issue-driven `v0.1.x` maintenance |

下载安装包：[GitHub Releases](https://github.com/Theopote/PlanSeed/releases/tag/v0.1.0-alpha) · 发布说明：[docs/alpha-v0.1-release-notes.md](docs/alpha-v0.1-release-notes.md) · 验收记录：[docs/alpha-v0.1-release-readiness.md](docs/alpha-v0.1-release-readiness.md)

## 快速开始

```bash
# 安装依赖（Python 3.12 + uv）
uv sync --dev

# 运行全部测试
uv run pytest

# 覆盖率报告（Phase 7.5-H：仅观察，无门槛）
uv run pytest --cov=packages --cov=solver --cov=backend --cov-report=term-missing

# 静态检查（与 CI 对齐；mypy 宽松，勿 --strict）
uv run ruff check .
uv run mypy packages solver backend
```

CI：push / PR 自动跑 pytest(+coverage 报告) · ruff · mypy · **OpenAPI→TS 契约漂移** · `pnpm --dir desktop build` · `cargo check`（见 `.github/workflows/ci.yml`）。  
**暂不**因 coverage&lt;90 失败。  
Windows sidecar（PyInstaller）仅手动 / release 工作流。

改 FastAPI / Pydantic API 模型后须同步契约：

```bash
uv run python scripts/export_openapi.py
pnpm --dir desktop generate:api
```

架构与历史 Phase：[docs/roadmap.md](docs/roadmap.md) · ADR：[docs/adr/](docs/adr/) · C4：[docs/c4.md](docs/c4.md)。

```bash
# 运行 solver demo
uv run python -m solver.demo

# 导出 Top 候选 SVG 调试图 → debug/
uv run python -m solver.visualize
```

### 桌面 UI（FastAPI + Vite / Tauri）

需要两个进程：

```bash
# 终端 1 — API（默认 8787）
uv run uvicorn backend.main:app --reload --port 8787

# 终端 2 — 前端
cd desktop
pnpm install
pnpm dev
# 浏览器打开 http://127.0.0.1:1420
```

Tauri 桌面壳（需本机 Rust toolchain）：

```bash
cd desktop
pnpm tauri:dev
```

可选：`VITE_API_BASE=http://127.0.0.1:8787`（默认即此地址）。

## 领域术语

```text
RequirementSpec  →  normalize  →  DesignProgram  →  generate  →  LayoutCandidate
```

- **RequirementSpec**：用户 / LLM 表达的需求（Hybrid Semantic Parser，非纯 LLM）
- **DesignProgram**：Normalizer 规范化后的建筑任务
- **LayoutCandidate**：Solver 生成的几何方案

LLM 不直接输出 DesignProgram 或坐标。详见 [docs/hybrid-semantic-parser.md](docs/hybrid-semantic-parser.md)。

## 文档

- [phases/phase-8-solver-2.0.md](docs/phases/phase-8-solver-2.0.md)
- [adr/](docs/adr/) · [c4.md](docs/c4.md)
- [architecture.md](docs/architecture.md)
- [schema.md](docs/schema.md)
- [solver.md](docs/solver.md)
- [scoring.md](docs/scoring.md)
- [hybrid-semantic-parser.md](docs/hybrid-semantic-parser.md)

## 贡献

欢迎 Issue / PR。约定与检查清单见 [CONTRIBUTING.md](CONTRIBUTING.md)。  
安全相关披露见 [SECURITY.md](SECURITY.md)。

## License

本项目以 [MIT License](LICENSE) 开源。

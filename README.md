# PlanSeed

Local-first、本地运行的独栋住宅生成式设计工具。

> AI understands the design intent.  
> The solver proves the geometry.  
> The evaluator explains the quality.  
> The architect remains in control.

## 开发

```bash
# 安装依赖（Python 3.12 + uv）
uv sync --dev

# 运行全部测试
uv run pytest

# 静态检查（与 CI 对齐；mypy 宽松，勿 --strict）
uv run ruff check .
uv run mypy packages solver backend
```

CI：push / PR 自动跑 pytest · ruff · mypy · `pnpm --dir desktop build` · `cargo check`（见 `.github/workflows/ci.yml`）。  
Windows sidecar（PyInstaller）仅手动 / release 工作流。

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

- **RequirementSpec**：用户 / LLM 表达的需求（LLM 阶段仍延后）
- **DesignProgram**：Normalizer 规范化后的建筑任务
- **LayoutCandidate**：Solver 生成的几何方案

## 当前阶段

**Desktop UI MVP**（进行中）：四区壳 + `POST /api/generate`。

Solver 拓扑与 Phase 3 评价已可用。LLM / 交互编辑 / 持久化仍延后。

见 [docs/roadmap.md](docs/roadmap.md)。

## 文档

- [architecture.md](docs/architecture.md)
- [schema.md](docs/schema.md)
- [solver.md](docs/solver.md)
- [scoring.md](docs/scoring.md)

## 参考原型

`reference/floorplan-generator.html` — GuillotineGenerator 逻辑来源。

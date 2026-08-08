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

# 运行 solver demo
uv run python -m solver.demo

# 导出 Top 候选 SVG 调试图 → debug/
uv run python -m solver.visualize
```

## 领域术语

```text
RequirementSpec  →  normalize  →  DesignProgram  →  generate  →  LayoutCandidate
```

- **RequirementSpec**：用户 / LLM 表达的需求（Phase 4 LLM 输出目标）
- **DesignProgram**：Normalizer 规范化后的建筑任务
- **LayoutCandidate**：Solver 生成的几何方案

`ProjectSpec` 仍保留作内部/过渡模型，逐步淡出用户-facing API。

## 当前阶段

**Phase 1.5 — Solver Reliability**（进行中）

见 [docs/roadmap.md](docs/roadmap.md)。FastAPI / Tauri / LLM 暂缓。

已完成：FloorAssignment、StairCore、Orientation 闭环、Quality regression。  
进行中：Architectural Zones（Guillotine 降为 RoomLayout strategy）。

## 文档

- [architecture.md](docs/architecture.md)
- [schema.md](docs/schema.md)
- [solver.md](docs/solver.md)
- [scoring.md](docs/scoring.md)

## 参考原型

`reference/floorplan-generator.html` — 已验证的递归切分算法原型（GuillotineGenerator 的逻辑来源）。

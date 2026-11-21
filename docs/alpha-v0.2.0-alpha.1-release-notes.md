# Alpha v0.2.0-alpha.1 — Patch Notes

> 稳定性补丁（不撤回 v0.2.0-alpha）· Tag：`v0.2.0-alpha.1`  
> 安装包：`PlanSeed_0.2.0_x64-setup.exe`

## 相对 v0.2.0-alpha

### P0 正确性

- 关系编译不再用空 `AccessGraph` 挡住住宅默认通行图；`ensure_access_graph` 合并默认软边
- `relation_intents` 编译后重建 `RoomGraph`；`near` / `adjacency` 语义分离
- Intent 增大面积时同步 `area-bound-*` 硬约束
- Optimize 优先请求体候选，避免未保存 Intent 结果被项目旧快照覆盖
- 候选 ID 含 strategy（含拓扑策略打标），跨策略同 seed 不再撞车

### P1 发布工程

- `uv.lock` 与 `0.2.0` 对齐；CI `uv lock --check`
- 安装包构建检查外部命令退出码；冒烟脚本先构建再取 setup

### 冒烟

引擎冒烟新增 Copilot：`intent/parse` → `apply` → `critique` → `optimize` → `strategy/generate`。

人工仍须：Desktop 窗口 READY、WebView2 Print、文件选择器 roundtrip、Benchmark ab_rate。

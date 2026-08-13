# Alpha v0.1 — Desktop 手测逐步清单（Release Gate B1 / A / C）

> 自动化已覆盖引擎 API 与装包 sidecar；**本页是 Desktop UI 关门步骤**。  
> 总览：[alpha-v0.1-hand-smoke.md](alpha-v0.1-hand-smoke.md)

## 0. 准备

```powershell
powershell -File scripts/preflight_release_gate.ps1
powershell -File scripts/prepare_desktop_hand_gate.ps1
powershell -File scripts/open_print_smoke.ps1
```

| 产物 | 路径 |
|------|------|
| NSIS 安装包 | `desktop/src-tauri/target/release/bundle/nsis/PlanSeed_0.1.0_x64-setup.exe` |
| Gate C 样本 | `debug/desktop-hand-gate/alpha-v0.1-hand-gate.planseed` |
| Print 对照 | `debug/print-smoke/index.html` |

---

## B1. 安装包启动 + 引擎已就绪

| 步骤 | 操作 | Pass |
|------|------|------|
| 1 | 双击 `PlanSeed_0.1.0_x64-setup.exe` 完成安装 | ☐ |
| 2 | 从开始菜单启动 **PlanSeed** | ☐ |
| 3 | 左栏引擎状态：**已就绪**（非「启动中→异常→已就绪」闪跳） | ☐ |
| 4 | 若异常：点 **重试引擎** 应恢复已就绪 | ☐ |

**Fail 记录：** 引擎状态文案、端口、是否误连外来 8787 服务。

---

## A. WebView2 Print（关门须在 Desktop）

Edge 打开 `debug/print-smoke/` 仅作对照；**Pass 以 Desktop 为准**。

| 步骤 | 操作 | Pass |
|------|------|------|
| 1 | Desktop：**导出** → **报告预览 / 打印 PDF**（或先 Generate 再导出） | ☐ |
| 2 | 报告预览浮层 → **打印 / PDF** | ☐ |
| 3 | 打印机：**Microsoft Print to PDF** · A4 纵向 | ☐ |
| 4 | 抽测 **P02** + **P06**：**打开…** → `PrintHand-P02_two_floor` / `PrintHand-P06_many_findings`（或 `generate_print_smoke_reports.py --seed-desktop`） | ☐ |
| 5 | 封面/目录不截断；平面 SVG 不跨页切开；中文无方框 | ☐ |

**禁止：** 对主窗口 `window.print()`（应走 iframe 内报告）。

详细矩阵：[phase-7.1-print-smoke.md](phase-7.1-print-smoke.md)

---

## C. `.planseed` Desktop 完整往返

API 保真单测已绿；本表验证 **文件选择器 + UI 状态**。

### 路径 A — 使用预制样本（快速）

| 步骤 | UI 位置 | 操作 | Pass |
|------|---------|------|------|
| C1 | 顶栏 | **导入包** → 选 `debug/desktop-hand-gate/alpha-v0.1-hand-gate.planseed` | ☐ |
| C2 | 平面图 / 候选条 | 候选 A 已选中；平面图有 SVG | ☐ |
| C3 | Inspector | 锁状态 / provenance 可见（generator=guillotine） | ☐ |
| C4 | **导出** → **报告预览 / 打印 PDF** | 报告可打开 | ☐ |
| C5 | **导出** → **当前层 2048** PNG 或 **当前层** SVG | 下载成功 | ☐ |

### 路径 B — 完整用户路径（推荐勾选一次）

| 步骤 | 操作 | Pass |
|------|------|------|
| C1 | 表单宽 11 深 13 → **生成布局**（或基准案例） | ☐ |
| C2 | Inspector：**锁定房间**（或拖拽后锁定） | ☐ |
| C3 | 可选：Inspector nudge / Regenerate | ☐ |
| C4 | 选中候选 → **保存** → **导出包** → 得到 `.planseed` | ☐ |
| C5 | **打开…** 删项目，或新装环境 | ☐ |
| C6 | **导入包** → 同一文件 | ☐ |
| C7 | 检视：RequirementSpec · Program · Candidates · revision · locks · mutations · provenance | ☐ |
| C8 | 再导出 SVG/PNG 一次成功 | ☐ |

### 导入后必查字段（Inspector / 需求面板）

- [ ] `requirement_spec.floor_count` / spaces 未丢
- [ ] `program.rooms` 与平面图房间一致
- [ ] `candidates[0].revision_status` / `revision_id`
- [ ] `locks.rooms` 非空（样本包应锁客厅）
- [ ] `mutations` 含 nudge 记录（样本包）
- [ ] `provenance.generator_strategy` = `guillotine`
- [ ] `provenance.selection_strategy` = `axis-diverse`
- [ ] `provenance.selection_version` = `axis-diversity-v1`（或当前 `SELECTION_VERSION`）
- [ ] `provenance.evaluation_version` = `residential-alpha-v1`
- [ ] `schema_versions.geometry_backend` = `rect`
- [ ] `schema_versions.assignment_strategy` = `heuristic`（Solver 2.0 字段未截断）

---

## 勾完后

1. 回写 [alpha-v0.1-hand-smoke.md](alpha-v0.1-hand-smoke.md) A/B/C 列
2. 回写 [alpha-v0.1-release-readiness.md](alpha-v0.1-release-readiness.md) §3–5
3. 方可称 **Alpha v0.1 Release Ready**

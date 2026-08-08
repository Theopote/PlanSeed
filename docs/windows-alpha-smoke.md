# Windows Alpha Smoke（Phase 3.6）

手测 / 半自动清单：确认装包引擎自启、身份探针、Generate、Compare。

## 前置

1. `uv sync --group build`
2. `pwsh scripts/build_backend_sidecar.ps1`
3. `pnpm --dir desktop tauri:build`
4. 用 NSIS 安装 `desktop/src-tauri/target/release/bundle/nsis/*-setup.exe`

## 快速健康检查（可选脚本）

```powershell
pwsh scripts/windows_alpha_smoke.ps1
```

脚本会：探测默认 `127.0.0.1:8787`（或 `$env:PLANSEED_PORT`）的 `/api/health` 身份契约，并 POST 基准 `/api/generate` + `/api/compare`。

若应用已打开且引擎在跑，可直接跑脚本；若端口空闲，请先启动 PlanSeed 桌面端再测。

## 手测 DoD

| # | 步骤 | 期望 |
|---|------|------|
| 1 | 安装并启动 PlanSeed | 窗口先出；左栏引擎 → **已就绪** |
| 2 | 外来服务占用 8787（非 planseed health） | 应用换端口自启，不 reuse 外来服务 |
| 3 | Generate（表单） | 出候选 + SVG；Inspector findings |
| 4 | 基准案例 | 同上 |
| 5 | Alt+点击另一候选 | Compare 表来自引擎 `/api/compare`（非前端算分） |
| 6 | 杀引擎进程 / 模拟崩溃 | 状态 → **异常**，出现 **重试引擎** |
| 7 | 重试引擎 | 回到 **已就绪** |
| 8 | 日志 | `%APPDATA%\com.planseed.app\logs\engine.log`（或 Tauri `app_log_dir`）含 startup / port / fatal |

> 实际 log 目录以本机 Tauri `app_log_dir` 为准（identifier 见 `tauri.conf.json`）。

## 不做

- macOS / Linux 装包冒烟（Alpha 后）
- Ollama / LLM

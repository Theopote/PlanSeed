# PlanSeed backend sidecar binaries

Tauri `bundle.externalBin` 期望此处存在带 **target triple** 后缀的可执行文件，例如：

```text
planseed-backend-x86_64-pc-windows-msvc.exe
planseed-backend-x86_64-apple-darwin
planseed-backend-aarch64-apple-darwin
planseed-backend-x86_64-unknown-linux-gnu
```

生成（在仓库根目录）：

```powershell
.\scripts\build_backend_sidecar.ps1
```

或：

```bash
bash scripts/build_backend_sidecar.sh
```

开发态（`tauri dev`）不依赖本目录：Rust `setup` 会用 `uv run python -m backend` 拉起引擎。

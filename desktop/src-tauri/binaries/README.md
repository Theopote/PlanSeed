# PlanSeed backend sidecar binaries

Tauri `bundle.externalBin` 期望此处存在带 **target triple** 后缀的可执行文件，例如：

```text
planseed-backend-x86_64-pc-windows-msvc.exe
```

## 开发期占位

`cargo check` / `tauri:dev` 需要文件存在。仓库根目录执行：

```powershell
rustc -O -o desktop/src-tauri/binaries/planseed-backend-x86_64-pc-windows-msvc.exe scripts/sidecar_stub.rs
```

（debug 模式仍优先 `uv run python -m backend`，不会真跑 stub。）

## 正式引擎

```powershell
.\scripts\build_backend_sidecar.ps1
```

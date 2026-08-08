# Sidecar 资源（PyInstaller --onedir）

正式产物目录：

```text
resources/planseed-backend/
  planseed-backend.exe   # Windows
  _internal/             # 依赖与运行时
```

生成：

```powershell
.\scripts\build_backend_sidecar.ps1
```

开发态 `tauri:dev` 仍用 `uv run python -m backend`，不依赖本目录真引擎。
`tauri.conf.json` 通过 `bundle.resources` 打包整目录（**不用** onefile / externalBin）。

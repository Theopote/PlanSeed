# Sidecar 资源（锁定：PyInstaller --onedir + bundle.resources）

**不**再使用 `externalBin`。onedir 是整目录（exe + `_internal` + runtime），由 Tauri `resources` 打包、Rust `Command` 托管进程。

## Canonical 路径（正式包唯一契约）

```text
{resource_dir}/planseed-backend/planseed-backend.exe   # Windows
{resource_dir}/planseed-backend/planseed-backend       # Unix
+ _internal/
```

`sidecar_path()` 正式只认这一条；其它探测仅 `debug_assertions`。

## 生成

```powershell
.\scripts\build_backend_sidecar.ps1
```

开发态 `tauri:dev` 仍用 `uv run python -m backend`，不依赖本目录真引擎。

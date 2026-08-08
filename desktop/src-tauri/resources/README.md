# Sidecar 资源（锁定：PyInstaller --onedir + bundle.resources）

**Desktop Alpha 平台写死：Windows 10/11 x64。** 不做并行 macOS/Linux 打包。

**不**再使用 `externalBin`。onedir 是整目录（exe + `_internal` + runtime），由 Tauri `resources` 打包、Rust `Command` 托管进程。

## Canonical 路径（正式包唯一契约）

```text
{resource_dir}/planseed-backend/planseed-backend.exe   # Windows Alpha
+ _internal/
```

`sidecar_path()` 正式只认这一条；其它探测仅 `debug_assertions`。

`tauri.conf.json` 必须用 **map** 把源目录映射到目标名（Windows 上 `resource_dir` = exe 目录）：

```json
"resources": { "resources/planseed-backend": "planseed-backend" }
```

列表写法会保留 `resources/` 前缀，导致正式包找不到引擎。

## 生成（主线）

```powershell
uv sync --group build
.\scripts\build_backend_sidecar.ps1
```

脚本内会 `uv sync --group build`，**不再** `pip install pyinstaller`。
PyInstaller 在 `[dependency-groups].build`，由 `uv.lock` 锁定。

开发态 `tauri:dev` 仍用 `uv run python -m backend`，不依赖本目录真引擎。

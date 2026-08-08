# 将 FastAPI 引擎打成 Tauri externalBin（Windows）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Triple = "x86_64-pc-windows-msvc"
$OutDir = Join-Path $Root "desktop\src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "[sidecar] installing PyInstaller…"
& uv run python -m pip install -q pyinstaller

$Entry = Join-Path $Root "scripts\sidecar_entry.py"
$Dist = Join-Path $Root "dist\sidecar"
$Name = "planseed-backend"

Write-Host "[sidecar] building $Name…"
& uv run pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name $Name `
  --distpath $Dist `
  --workpath (Join-Path $Root "build\sidecar") `
  --paths $Root `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols `
  --hidden-import uvicorn.protocols.http `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.lifespan `
  --hidden-import uvicorn.lifespan.on `
  $Entry

$Built = Join-Path $Dist "$Name.exe"
$Target = Join-Path $OutDir "$Name-$Triple.exe"
Copy-Item -Force $Built $Target
Write-Host "[sidecar] wrote $Target"
Write-Host "[sidecar] next: install Rust toolchain, then pnpm --dir desktop tauri:build"

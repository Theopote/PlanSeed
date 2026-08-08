# 将 FastAPI 引擎打成 Tauri 资源目录（Windows，PyInstaller --onedir）
# onedir：冷启动更快，且比 onefile 更不易被 Defender 误拦。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ResRoot = Join-Path $Root "desktop\src-tauri\resources"
$TargetDir = Join-Path $ResRoot "planseed-backend"
New-Item -ItemType Directory -Force -Path $ResRoot | Out-Null

Write-Host "[sidecar] installing PyInstaller…"
& uv run python -m pip install -q pyinstaller

$Entry = Join-Path $Root "scripts\sidecar_entry.py"
$Dist = Join-Path $Root "dist\sidecar"
$Name = "planseed-backend"

Write-Host "[sidecar] building $Name (--onedir)…"
& uv run pyinstaller `
  --noconfirm `
  --clean `
  --onedir `
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

$BuiltDir = Join-Path $Dist $Name
if (-not (Test-Path $BuiltDir)) {
  throw "PyInstaller output missing: $BuiltDir"
}

if (Test-Path $TargetDir) {
  Remove-Item -Recurse -Force $TargetDir
}
Copy-Item -Recurse -Force $BuiltDir $TargetDir

$Exe = Join-Path $TargetDir "$Name.exe"
if (-not (Test-Path $Exe)) {
  throw "engine exe missing: $Exe"
}

Write-Host "[sidecar] wrote onedir -> $TargetDir"
Write-Host "[sidecar] next: pnpm --dir desktop tauri:build"

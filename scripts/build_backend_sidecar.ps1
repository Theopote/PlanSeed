# 将 FastAPI 引擎打成 Tauri 资源目录（Windows，PyInstaller --onedir）
# Desktop Alpha 唯一主线平台：Windows 10/11 x64（见 docs/phase-3.6-runtime-reliability.md）
# onedir：冷启动更快，且比 onefile 更不易被 Defender 误拦。
# 注意：Write-Host 字符串只用 ASCII，避免 Windows PowerShell 5 无 BOM UTF-8 解析失败。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# 嵌套 powershell / 非登录 shell 常缺 PATH；补常见 uv 安装位
# 强制 @()：单元素 Where-Object 结果可能变成字符串，此时 [0] 会取到首字符（如 "C"）
$UvCandidates = @(
  @(
    (Get-Command uv -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
    (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe")
  ) | Where-Object { $_ -and (Test-Path $_) }
)
if ($UvCandidates.Count -lt 1) {
  throw "uv not found. Install uv and ensure ~/.local/bin is on PATH."
}
$Uv = [string]$UvCandidates[0]
if (-not ((Test-Path -LiteralPath $Uv) -and ($Uv -match '(?i)(^|[\\/])uv(\.exe)?$'))) {
  throw "uv candidate is not an executable path: $Uv"
}

$ResRoot = Join-Path $Root "desktop\src-tauri\resources"
$TargetDir = Join-Path $ResRoot "planseed-backend"
New-Item -ItemType Directory -Force -Path $ResRoot | Out-Null

function Assert-Exit([int]$code, [string]$step) {
  if ($code -ne 0) { throw "FAIL: $step (exit $code)" }
}

$Entry = Join-Path $Root "scripts\sidecar_entry.py"
$Dist = Join-Path $Root "dist\sidecar"
$Name = "planseed-backend"
$BuiltDir = Join-Path $Dist $Name

# 清理旧产物，避免失败后仍被 Test-Path 当成成功
if (Test-Path $Dist) {
  Remove-Item -Recurse -Force $Dist
}
if (Test-Path $TargetDir) {
  Remove-Item -Recurse -Force $TargetDir
}

Write-Host "[sidecar] syncing build group (PyInstaller via uv.lock)..."
& $Uv sync --group build
Assert-Exit $LASTEXITCODE "uv sync --group build"

Write-Host "[sidecar] building $Name (onedir)..."
& $Uv run --group build pyinstaller `
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
  --hidden-import resvg_py `
  --collect-all resvg_py `
  --collect-binaries resvg_py `
  $Entry
Assert-Exit $LASTEXITCODE "pyinstaller"

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

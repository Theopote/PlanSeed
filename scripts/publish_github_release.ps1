# Publish PlanSeed Alpha NSIS installer to GitHub Releases.
# Usage (interactive PowerShell / Windows Terminal — not non-interactive agent shells):
#   powershell -ExecutionPolicy Bypass -File scripts/publish_github_release.ps1
#
# Optional:
#   $env:PLANSEED_RELEASE_TAG = "v0.1.1-alpha"
#   $env:PLANSEED_SETUP_EXE = "path\to\PlanSeed_0.1.1_x64-setup.exe"

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
. "$PSScriptRoot\_release_path.ps1"

$Tag = if ($env:PLANSEED_RELEASE_TAG) { $env:PLANSEED_RELEASE_TAG } else { "v0.1.1-alpha" }
$Setup = if ($env:PLANSEED_SETUP_EXE) { $env:PLANSEED_SETUP_EXE } else { Get-PlanSeedNsisSetup $Root }

if (-not (Test-Path $Setup)) {
  throw "Installer not found: $Setup`nBuild first: scripts/build_backend_sidecar.ps1 then pnpm --dir desktop tauri:build"
}

$setupName = Split-Path $Setup -Leaf

Write-Host "== checking gh auth =="
$authOk = $false
try {
  gh auth status 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $authOk = $true }
} catch {
  $authOk = $false
}

if (-not $authOk) {
  Write-Host "Not logged in. Starting browser login (complete in browser, then return here)..."
  gh auth login -h github.com -p https -w
  if ($LASTEXITCODE -ne 0) { throw "gh auth login failed" }
}

$existing = gh release view $Tag 2>$null
if ($LASTEXITCODE -eq 0) {
  throw "Release $Tag already exists. Delete it or set PLANSEED_RELEASE_TAG to a new tag."
}

$Notes = @"
## PlanSeed Alpha v0.1.1

**Platform:** Windows 10/11 x64 only · solver 0.6 · 8.4.1 irregular pipeline (Engineering)

### Install
1. Download ``$setupName``
2. Run the installer
3. Launch **PlanSeed** and wait until the engine shows Ready

### Notes
- Local-first desktop app (Tauri + embedded solver engine)
- Natural-language parsing needs a local [Ollama](https://ollama.com) install (optional)
- Product default geometry remains **rect**; irregular site is engineering-only
- This is an **Alpha** build for early testing — not a final product release

See full notes: ``docs/alpha-v0.1.1-release-notes.md``

### Smoke (optional, after install)
With the app running:
``````
powershell -File scripts/windows_alpha_smoke.ps1
``````
"@

Write-Host "== creating release $Tag =="
gh release create $Tag $Setup `
  --title "PlanSeed Alpha v0.1.1" `
  --notes $Notes `
  --prerelease

if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }

Write-Host "== done =="
gh release view $Tag --json url,tagName,assets --jq "{url: .url, tag: .tagName, assets: [.assets[].name]}"

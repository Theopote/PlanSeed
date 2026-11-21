# Publish PlanSeed Alpha NSIS installer to GitHub Releases.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/publish_github_release.ps1
#
# Optional:
#   $env:PLANSEED_RELEASE_TAG = "v0.2.0-alpha.1"
#   $env:PLANSEED_SETUP_EXE = "path\to\PlanSeed_0.2.0_x64-setup.exe"

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
. "$PSScriptRoot\_release_path.ps1"

$Tag = if ($env:PLANSEED_RELEASE_TAG) { $env:PLANSEED_RELEASE_TAG } else { "v0.2.0-alpha.1" }
$Setup = if ($env:PLANSEED_SETUP_EXE) { $env:PLANSEED_SETUP_EXE } else { Get-PlanSeedNsisSetup $Root }

if (-not (Test-Path $Setup)) {
  throw "Installer not found: $Setup`nBuild first: scripts/build_backend_sidecar.ps1 then pnpm --dir desktop tauri:build"
}

$setupName = Split-Path $Setup -Leaf

Write-Host "== checking gh auth =="
$authOk = $false
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
gh auth status *> $null
if ($LASTEXITCODE -eq 0) { $authOk = $true }
$ErrorActionPreference = $prevEap

if (-not $authOk) {
  Write-Host "Not logged in. Starting browser login (complete in browser, then return here)..."
  gh auth login -h github.com -p https -w
  if ($LASTEXITCODE -ne 0) { throw "gh auth login failed" }
}

$releaseExists = $false
try {
    gh release view $Tag 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $releaseExists = $true }
} catch {
    $releaseExists = $false
}
if ($releaseExists) {
  throw "Release $Tag already exists. Delete it or set PLANSEED_RELEASE_TAG to a new tag."
}

$Notes = @"
## PlanSeed Alpha v0.2.0-alpha.1

**Platform:** Windows 10/11 x64 only · solver 0.6 · stability patch on Architect Workflow / Copilot

### Install
1. Download ``$setupName``
2. Run the installer
3. Launch **PlanSeed** and wait until the engine shows Ready

### Fixes (vs v0.2.0-alpha)
- Default residential AccessGraph no longer blocked by empty relation compile
- RoomGraph rebuilt after relation intents; near ≠ adjacency
- Intent area changes sync hard ``area-bound-*`` constraints
- Optimize prefers request-body candidate over stale project snapshot
- Candidate IDs include strategy (no cross-strategy seed collisions)
- ``uv.lock`` / CI lock check; installer scripts check exit codes

See: ``docs/alpha-v0.2.0-alpha.1-release-notes.md``

### Notes
- Still Alpha — Design Benchmark **ab_rate** needs human review
- Ollama optional for NL; geometry default remains **rect**
"@

Write-Host "== creating release $Tag =="
gh release create $Tag $Setup `
  --title "PlanSeed Alpha v0.2.0-alpha.1" `
  --notes $Notes `
  --prerelease

if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }

Write-Host "== done =="
gh release view $Tag --json url,tagName,assets --jq "{url: .url, tag: .tagName, assets: [.assets[].name]}"

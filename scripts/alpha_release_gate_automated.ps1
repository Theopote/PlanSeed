# Alpha v0.1 — 可自动化 Release Gate（不含 WebView2 Print / 安装包手测）
# Usage:
#   powershell -File scripts/alpha_release_gate_automated.ps1
#   powershell -File scripts/alpha_release_gate_automated.ps1 -SkipPytest
#   powershell -File scripts/alpha_release_gate_automated.ps1 -StartBackend
#
# 手测仍须完成：docs/alpha-v0.1-hand-smoke.md §A/B/C

param(
    [switch]$SkipPytest,
    [switch]$SkipEngine,
    [switch]$SkipPrintHtml,
    [switch]$SkipSidecar,
    [switch]$SkipInstaller,
    [switch]$IncludeDesktopShell,
    [switch]$RebuildSidecar,
    [switch]$StartBackend
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_release_path.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Assert-Exit([int]$code, [string]$step) {
    if ($code -ne 0) { throw "FAIL: $step (exit $code)" }
    Write-Host "OK: $step"
}

Write-Host "== Alpha v0.1 automated release gate =="

if (-not $SkipPytest) {
    Write-Host "-- pytest (release regression subset) --"
    $basetemp = Join-Path $Root ".pytest_basetemp"
    New-Item -ItemType Directory -Force -Path $basetemp | Out-Null
    uv run pytest `
        backend/tests/test_projects_api.py `
        backend/tests/test_png_export.py `
        backend/tests/test_svg_export.py `
        backend/tests/test_report_json_export.py `
        backend/tests/test_compare_api.py `
        backend/tests/test_nl_parse_api.py `
        solver/tests/test_quality_regression.py `
        solver/tests/test_pipeline.py `
        solver/tests/test_checker.py `
        packages/llm/tests/test_enrich.py `
        -q --no-cov `
        --basetemp=$basetemp
    Assert-Exit $LASTEXITCODE "pytest release subset"
}

$backendProc = $null
if ($StartBackend) {
    Write-Host "-- starting backend (background) --"
    $backendProc = Start-Process -FilePath "uv" -ArgumentList @(
        "run", "python", "-m", "backend"
    ) -WorkingDirectory $Root -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

try {
    if (-not $SkipEngine) {
        Write-Host "-- engine smoke (health / generate / compare / export / report / .planseed) --"
        uv run python scripts/alpha_release_engine_smoke.py
        Assert-Exit $LASTEXITCODE "alpha_release_engine_smoke.py"

        Write-Host "-- windows_alpha_smoke.ps1 --"
        & "$PSScriptRoot/windows_alpha_smoke.ps1"
    }

    if (-not $SkipSidecar) {
        Write-Host "-- sidecar release smoke (PyInstaller onedir) --"
        $sidecarArgs = @()
        if ($RebuildSidecar) { $sidecarArgs += "-RebuildSidecar" }
        & "$PSScriptRoot/sidecar_release_smoke.ps1" @sidecarArgs
    }

    if (-not $SkipInstaller) {
        Write-Host "-- installer release smoke (NSIS silent -> backend) --"
        & "$PSScriptRoot/installer_release_smoke.ps1"
    }

    if ($IncludeDesktopShell) {
        Write-Host "-- desktop shell smoke (NSIS -> app.exe -> health) --"
        & "$PSScriptRoot/desktop_shell_smoke.ps1"
    }

    if (Test-Path (Join-Path $Root "debug\desktop-hand-gate\alpha-v0.1-hand-gate.planseed")) {
        Write-Host "-- validate hand-gate .planseed fixture --"
        uv run python scripts/validate_hand_gate_fixture.py
        Assert-Exit $LASTEXITCODE "validate_hand_gate_fixture.py"
    } else {
        Write-Host "SKIP: hand-gate fixture (run prepare_desktop_hand_gate.py once)"
    }

    if (-not $SkipPrintHtml) {
        Write-Host "-- print smoke HTML fixtures (hand-test input only) --"
        uv run python scripts/generate_print_smoke_reports.py
        Assert-Exit $LASTEXITCODE "generate_print_smoke_reports.py"
    }
}
finally {
    if ($null -ne $backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "== automated gate passed =="
Write-Host "Remaining manual Release Gate (UI only):"
Write-Host "  powershell -File scripts/start_desktop_hand_session.ps1"
Write-Host "  Or: docs/alpha-v0.1-desktop-hand-gate.md"
Write-Host "  A) WebView2 Print   B1) READY + Retry   C) .planseed import/export UI"

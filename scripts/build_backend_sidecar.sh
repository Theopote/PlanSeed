#!/usr/bin/env bash
# [DEFERRED] macOS / Linux sidecar — Desktop Alpha 仅 Windows（见 docs/phase-3.6-runtime-reliability.md）。
# Alpha 跑通前请用：scripts/build_backend_sidecar.ps1
# 本脚本保留供后续平台扩展，不是当前主线。
set -euo pipefail
echo "Desktop Alpha platform is Windows 10/11 x64." >&2
echo "Use scripts/build_backend_sidecar.ps1 until Alpha ships." >&2
echo "Re-enable this script only after Windows Alpha is done." >&2
exit 1

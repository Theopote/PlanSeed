#!/usr/bin/env bash
# 将 FastAPI 引擎打成 Tauri externalBin（macOS / Linux）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "$(uname -s)" in
  Darwin)
    ARCH="$(uname -m)"
    if [[ "$ARCH" == "arm64" ]]; then
      TRIPLE="aarch64-apple-darwin"
    else
      TRIPLE="x86_64-apple-darwin"
    fi
    ;;
  Linux)
    TRIPLE="x86_64-unknown-linux-gnu"
    ;;
  *)
    echo "unsupported OS; use build_backend_sidecar.ps1 on Windows" >&2
    exit 1
    ;;
esac

OUT="$ROOT/desktop/src-tauri/binaries"
mkdir -p "$OUT"
uv run python -m pip install -q pyinstaller

NAME="planseed-backend"
DIST="$ROOT/dist/sidecar"
uv run pyinstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name "$NAME" \
  --distpath "$DIST" \
  --workpath "$ROOT/build/sidecar" \
  --paths "$ROOT" \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  "$ROOT/scripts/sidecar_entry.py"

cp -f "$DIST/$NAME" "$OUT/$NAME-$TRIPLE"
chmod +x "$OUT/$NAME-$TRIPLE"
echo "[sidecar] wrote $OUT/$NAME-$TRIPLE"

#!/usr/bin/env bash
# 将 FastAPI 引擎打成 Tauri 资源目录（macOS / Linux，PyInstaller --onedir）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RES="$ROOT/desktop/src-tauri/resources"
TARGET="$RES/planseed-backend"
mkdir -p "$RES"

uv run python -m pip install -q pyinstaller

NAME="planseed-backend"
DIST="$ROOT/dist/sidecar"
uv run pyinstaller \
  --noconfirm \
  --clean \
  --onedir \
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

BUILT="$DIST/$NAME"
rm -rf "$TARGET"
cp -R "$BUILT" "$TARGET"
chmod +x "$TARGET/$NAME" || true
echo "[sidecar] wrote onedir -> $TARGET"

"""导出 FastAPI OpenAPI → desktop/openapi.json（稳定排序，供 TS 生成）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desktop" / "openapi.json"


def main() -> int:
    # 保证仓库根在 path 上
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from backend.main import create_app

    app = create_app()
    schema = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

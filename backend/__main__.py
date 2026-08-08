"""python -m backend — 本地引擎入口（端口可被环境变量覆写）。"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("PLANSEED_HOST", "127.0.0.1")
    port = int(os.environ.get("PLANSEED_PORT", "8787"))
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        log_level=os.environ.get("PLANSEED_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
